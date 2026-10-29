#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
contract_redactor.py
====================
合同脱敏改写器 —— 读取 detection 报告 + 用户的选择（或 --types），
对 .docx / .pdf / .txt 文档执行**真正**的脱敏改写，输出新文件。

设计目标
--------
1. **完全离线**：与 detector 共享同一个 enforce_offline() 默认开启。
2. **不损坏版式**：docx 走「run 级回填」，只在文本 run 中做字符替换；
   pdf 走「bbox 白块」，不破坏底图；txt 走「原文 diff 替换」。
3. **可审计**：输出文件旁附一份 *.redaction.log（哪些位置、用何种规则、
   替换前后值），便于事后追溯与人工复核。
4. **可对接复核页**：读取 detector 的 selection.json（用户在 HTML 上
   按高中低分类筛选后下载的文件），也可 --types X,Y 直接指定。

命令行示例
----------
    # 1) 使用 detector 输出的 .selection.json
    python contract_redactor.py 合同.docx --selection 合同.selection.json

    # 2) 直接指定类型
    python contract_redactor.py 合同.pdf --types ID_CARD,PHONE_MOBILE,PERSON_NAME

    # 3) 与 detector 配合一气呵成
    python contract_sensitive_detector.py 合同.docx --format html,selection
    python contract_redactor.py 合同.docx --selection 合同.selection.json

    # 4) 起一个本地 127.0.0.1 服务，让复核页一键调用
    python contract_redactor.py --serve --port 8765

输出
----
    <原文件名>_脱敏.<原扩展名>        脱敏后的文档
    <原文件名>_脱敏.redaction.log     改写明细（JSON Lines）
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import socket
import sys
import time
import uuid
from datetime import datetime
import threading
import html as _html
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# 复用 detector 的纯离线算法、校验位、类型元数据、文档解析、识别引擎。
import contract_sensitive_detector as D
from contract_sensitive_detector import (
    TYPE_META,
    Block,
    Document,
    DetectorEngine,
    Settings,
    extract_docx,
    extract_pdf,
    extract_text_file,
    is_placeholder,
    load_allowlist,
    load_rules_md,
    mask_value,
)

# --------------------------------------------------------------------- 常量 --

__version__ = "1.4.1"
ENGINE_NAME = "contract_redactor"


# --------------------------------------------------------------------- 数据结构


@dataclass
class RedactOp:
    """一次改写动作：在 [start, end) 区间内用 replacement 替换原文。"""
    start: int                  # 原始全文偏移（来自 detection 报告）
    end: int
    type_id: str
    label: str
    severity: str
    confidence: float
    value: str                  # 该次出现的真实原文
    replacement: str            # 替换后
    location: str = ""
    page: Optional[int] = None
    bbox: Optional[List[float]] = None
    entity_value: str = ""      # 所属实体的代表值（同一实体编号一致，用它查号）
    block_index: int = -1


# --------------------------------------------------------------------- 文档重写器


class BaseRedactor:
    """改写器接口。每种格式一个子类。"""

    file_type: str = ""

    def __init__(self, source: str, full_text: str, ops: List[RedactOp]):
        self.source = source
        self.full_text = full_text
        self.ops = sorted(ops, key=lambda o: o.start, reverse=True)  # 从后往前改

    # 子类必须实现
    def rewrite(self, dst: str) -> Dict[str, Any]:
        raise NotImplementedError

    # 通用工具：把 ops 应用到一段纯文本（txt/解析后内容）
    def apply_to_text(self, text: str) -> Tuple[str, int, int]:
        applied, skipped = 0, 0
        out = text
        # 由后向前避免偏移变化
        for op in sorted(self.ops, key=lambda o: o.start, reverse=True):
            seg = text[op.start:op.end]
            if seg != op.value:
                # 漂移防御：若当前文本不再匹配，跳过
                skipped += 1
                continue
            out = out[:op.start] + op.replacement + out[op.end:]
            applied += 1
        return out, applied, skipped


# ---------------------------------------------- DOCX 改写（run 级 XML 回填）


class DocxRedactor(BaseRedactor):
    """docx 改写：在段落级别替换文本，保留原有 run 的样式。

    算法
    ----
    1. detector 把每个段落当成一个 block，block 文本 = 该段落所有
       `<w:t>` 节点的 text 拼接（去掉 \\n）。
    2. 本改写器按相同顺序遍历段落（含页眉页脚），
       对每个段落：
         a) 收集所有 `<w:t>`，拼成 para_text；
         b) 校验 para_text == block_text；漂移则跳过；
         c) 对每个 op，把它映射到若干 `<w:t>` 上的字符区间，
            再把 replacement 按比例切分到这些 `<w:t>` 中替换。

    跨多个 `<w:t>` 的 op（如一个手机号被拆在两个 run 里）会被切分成
    「第一段 + 后续段」形式写入。replacement 按各段原字符数比例切。
    """
    file_type = "docx"

    W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def rewrite(self, dst: str) -> Dict[str, Any]:
        from docx_text import DocxText, paragraph_map, replace_ranges
        package = DocxText(self.source)
        texts = [paragraph_map(p)[0].rstrip("\n") for _, p in package.entries]
        if "\n".join(texts) != self.full_text:
            raise RuntimeError("识别与改写文本不一致，已停止导出")
        spans = []
        start = 0
        for text in texts:
            spans.append((start, start+len(text))); start += len(text)+1
        grouped = {}
        for op in self.ops:
            for i, (start, end) in enumerate(spans):
                if start <= op.start < op.end <= end:
                    grouped.setdefault(i, []).append((op.start-start, op.end-start, op.replacement, op.value))
                    break
            else:
                raise RuntimeError("替换位置跨段或超出范围，已停止导出")
        for i, replacements in grouped.items():
            replace_ranges(package.entries[i][1], replacements)
        package.save(dst)
        return {"applied": len(self.ops), "skipped": 0}

# ---------------------------------------------- PDF 改写（bbox 白块 + 可选文字层）


class PdfRedactor(BaseRedactor):
    """pdf 改写：对含命中的页面**栅格化**为图片，在图片上画白块，
    再用 reportlab 把图片贴回 PDF。

    为什么栅格化？
    --------------
    法律 / 财务场景要求 PDF 脱敏后**绝对**不能从文本层恢复原数据。
    简单地「在原内容流上盖白块」会让原文本仍保留在 PDF 文本层里，
    复制粘贴就能泄密。这里采用「命中页 → 渲染成位图 → 画白块 →
    重新合成 PDF」的路径，输出 PDF 不含原文本，安全级别最高。
    """
    file_type = "pdf"

    def rewrite(self, dst: str) -> Dict[str, Any]:
        import pypdfium2 as pdfium
        from PIL import ImageDraw
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from pypdf import PdfReader, PdfWriter
        groups = {}
        for op in self.ops:
            if not op.bbox or op.page is None:
                raise RuntimeError("PDF 候选项缺少坐标，不能安全导出")
            groups.setdefault(op.page, []).append(op)
        if not groups:
            shutil.copyfile(self.source, dst)
            return {"applied": 0, "skipped": 0}
        reader = PdfReader(self.source)
        writer = PdfWriter()
        pdf = pdfium.PdfDocument(self.source)
        temporary = dst+".writing"
        try:
            for index, original in enumerate(reader.pages):
                ops = groups.get(index+1, [])
                if not ops:
                    writer.add_page(original)
                    continue
                page = pdf[index]
                bitmap = page.render(scale=200/72)
                image = bitmap.to_pil().convert('RGB')
                width, height = page.get_width(), page.get_height()
                draw = ImageDraw.Draw(image)
                for op in ops:
                    x0, y0, x1, y1 = op.bbox
                    draw.rectangle((x0*image.width/width, y0*image.height/height,
                                    x1*image.width/width, y1*image.height/height), fill='white')
                # One page at a time; never retain a list of full-resolution PNGs.
                buffer = io.BytesIO()
                output = canvas.Canvas(buffer, pagesize=(width, height))
                output.drawImage(ImageReader(image), 0, 0, width=width, height=height)
                output.showPage(); output.save()
                writer.add_page(PdfReader(buffer).pages[0])
                image.close(); bitmap.close(); page.close()
            with open(temporary, 'wb') as stream: writer.write(stream)
            os.replace(temporary, dst)
        finally:
            pdf.close()
            if os.path.exists(temporary): os.remove(temporary)
        return {"applied": len(self.ops), "skipped": 0}


# ---------------------------------------------- TXT 改写（直接字符串替换）


class TextRedactor(BaseRedactor):
    """txt/md/纯文本改写：直接按 char-offset 做字符串切片替换。"""
    file_type = "txt"

    def rewrite(self, dst: str) -> Dict[str, Any]:
        # 优先用 detector 给出的 full_text（已对齐 offset）；仅当不可用时才读源文件
        text = self.full_text
        if not text:
            with open(self.source, "r", encoding="utf-8") as f:
                text = f.read()
        new_content, applied, skipped = self.apply_to_text(text)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(new_content)
        return {"applied": applied, "skipped": skipped}


# --------------------------------------------------- 把 detector 输出转成 ops --


def build_ops_from_report(report: Dict[str, Any], enabled_types: set,
                          enabled_items: Optional[List[Dict[str, Any]]] = None
                          ) -> Tuple[List[RedactOp], str]:
    """从 detector 的 .sensitive.json 报告 + 用户勾选的类型集合构造 ops。

    enabled_items：复核页里被逐个保留的「位置」清单，元素形如
        {"type": "PERSON_NAME", "offset": [start, end]}
    start/end 是该次出现在全文里的**绝对偏移**（复核页 mark 的 s/e）。
    注意不能用「实体内部的 occurrence 序号」做键 —— 每个实体的序号都从 0 重新开始，
    会把所有实体的第一处误判为同一处（踩过的坑）。
    传 None 表示不按位置过滤（命令行 --types 的用法）。
    """
    keep: Optional[set] = None
    if enabled_items is not None:
        keep = set()
        for mi in enabled_items:
            t = mi.get("type")
            off = mi.get("offset")
            if not t or not isinstance(off, (list, tuple)) or len(off) != 2:
                continue
            keep.add((t, int(off[0]), int(off[1])))

    ops: List[RedactOp] = []
    for it in report["items"]:
        if it["type"] not in enabled_types:
            continue
        replacement = mask_value(it["value"], it["type"])
        for o in it["occurrences"]:
            if keep is not None and (it["type"], o["offset"][0], o["offset"][1]) not in keep:
                continue
            ops.append(RedactOp(
                start=o["offset"][0],
                end=o["offset"][1],
                type_id=it["type"],
                label=it["label"],
                severity=it["severity"],
                confidence=it["confidence"],
                # 真实字面文本：同一实体的不同写法（全称/简称、带不含空格）各自还原
                value=o.get("text") or it["value"],
                replacement=replacement,
                location=o.get("location", ""),
                page=o.get("page"),
                bbox=o.get("bbox"),
                entity_value=it["value"],
                block_index=o.get("block_index", -1),
            ))

    if keep is not None and len(ops) != len(keep):
        raise RuntimeError("复核位置与当前识别结果不一致，请重新复核；不会扩大替换范围")

    full_text = report.get("_full_text", "")
    return ops, full_text


def load_selection(path: str) -> Dict[str, Any]:
    """读取 detector 复核页导出的 selection.json。

    兼容两种形态：
      - detector v1 直接的 {"source":..., "enabled_types":[...]}
      - detector 复核页的 selection（已封装）
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_report(report_path: str) -> Dict[str, Any]:
    """读取 detector 的 *.sensitive.json（包含每条 occurrence 的 offset/bbox/value）。"""
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------- 主流程：检测 → 选择 → 改写


def redact_file(source: str,
                selection: Optional[Dict[str, Any]] = None,
                types: Optional[Sequence[str]] = None,
                out_path: Optional[str] = None,
                rules_path: Optional[str] = None,
                min_confidence: float = 0.5,
                min_severity: str = "low",
                allowlist: Optional[Sequence[str]] = None,
                write_log: bool = True,
                restore_mode: bool = False,
                export_mode: Optional[str] = None,
                ) -> Dict[str, Any]:
    """对单个文件执行「检测 → 选择 → 改写」的端到端流程。

    selection 与 types 至少要有一个。

    restore_mode=True 时
    ------------------
    改写后的 docx / pdf 把所有替换项写成 [label#N] 占位符，并在同目录
    输出 <stem>.mapping.json，之后可用 restore_file() 一次性还原回原文
    （占位符 ↔ 原文一一对应）。原文映射只保存在 JSON，不嵌入 Word。当源是 .pdf 时，占位符会落在栅格化后的图片层上，
    所以 **PDF 模式仅占位生成 mapping，不实际写「占位 docx」**；可还原的始终是 docx。
    """
    if export_mode not in (None, "external", "reversible"):
        raise ValueError("未知导出模式")
    # Old callers remain compatible, but no new document may embed original data.
    if export_mode == "reversible" or (restore_mode and export_mode is None):
        export_mode = "external"
    if export_mode:
        restore_mode = True
    if export_mode == "external":
        write_log = False
    if not selection and not types:
        raise ValueError("必须提供 --selection 或 --types")

    settings = D.load_settings(rules_path, min_confidence=min_confidence, min_severity=min_severity)
    if allowlist:
        settings.allowlist = set(allowlist)

    # 2) 用 detector 跑一次（保证报告与 detector 完全对齐）
    engine = DetectorEngine(settings)
    doc = _load_doc(source)
    if export_mode == "external" and doc.warnings:
        raise RuntimeError("存在尚未检查的页面："+"；".join(doc.warnings))
    candidates = engine.scan_document(doc)

    # 把 allowlist 过滤也加进去
    if settings.allowlist:
        candidates = [c for c in candidates if c.value not in settings.allowlist]

    full_text = "\n".join(b.text.rstrip("\n") for b in doc.blocks)
    report = D.build_report(doc, candidates, settings)
    report["_full_text"] = full_text

    # 3) 选择
    if selection:
        enabled_types = set(selection.get("enabled_types", []))
        # 复核页会带上逐个位置的白名单；命令行用法没有这个键 → None（不过滤）
        sel_items = selection.get("items")
    else:
        enabled_types = set(types or [])
        sel_items = None

    # 4) 构造 ops
    ops, full_text = build_ops_from_report(report, enabled_types, sel_items)

    # 4.b) restore_mode：把所有 replacement 换成 [label#N]，并累计 mapping
    #      编号规则：同一个实体（同一个人/企业，含简称）在整篇里**共用同一个编号**，
    #      例如「张三」出现 10 次全部是 [自然人姓名#1]。编号由 detector 的
    #      EntityNumberer 统一分配，保证与复核页、mapping.json 三处完全一致。
    mapping_records: List[Dict[str, Any]] = []
    if restore_mode:
        numberer = D.EntityNumberer(report.get("items") or [])
        new_ops: List[RedactOp] = []
        for op in ops:
            # 查号用的是「实体代表值」而非本次出现的字面文本，
            # 保证同一实体的全称/简称拿到同一个编号。
            placeholder = numberer.placeholder(
                op.type_id, op.entity_value or op.value, op.label)
            mapping_records.append({
                "type": op.type_id,
                "label": op.label,
                "severity": op.severity,
                "original": op.value,
                "entity_value": op.entity_value or op.value,
                "placeholder": placeholder,
                "masked": op.replacement,
                "start": op.start,
                "end": op.end,
                "page": op.page,
                "location": op.location,
                "block_index": op.block_index,
                "bbox": op.bbox,
                "confidence": op.confidence,
            })
            new_ops.append(RedactOp(
                start=op.start, end=op.end, type_id=op.type_id,
                label=op.label, severity=op.severity,
                confidence=op.confidence, value=op.value,
                replacement=placeholder, location=op.location,
                page=op.page, bbox=op.bbox,
                entity_value=op.entity_value, block_index=op.block_index,
            ))
        ops = new_ops

    # 5) 选改写器
    ext = os.path.splitext(source)[1].lower()
    if ext in (".docx",):
        redactor = DocxRedactor(source, full_text, ops)
    elif ext == ".pdf":
        redactor = PdfRedactor(source, full_text, ops)
    elif ext in (".txt", ".md", ".markdown", ""):
        redactor = TextRedactor(source, full_text, ops)
    else:
        raise RuntimeError(f"不支持的文件格式：{ext}")

    # 6) 决定输出路径
    if not out_path:
        stem = os.path.splitext(os.path.basename(source))[0]
        out_path = os.path.join(os.path.dirname(source) or ".",
                                f"{stem}_脱敏{ext or '.txt'}")

    if os.path.realpath(source) == os.path.realpath(out_path):
        raise ValueError("输出路径不能覆盖原文件")

    # 7) 改写
    if ext == ".docx" and export_mode == "external":
        from docx_text import DocxText
        DocxText(source).sanitize_external()  # Validate before creating any output.
    result = redactor.rewrite(out_path)
    if ext == ".docx" and export_mode == "external":
        clean = DocxText(out_path); clean.sanitize_external(); clean.save(out_path)

    # 7.b) 原文映射只写入单独 JSON，绝不嵌入脱敏 Word。
    mapping_path: Optional[str] = None
    if restore_mode:
        mapping_path = out_path + ".mapping.json"
        sha = ""
        try:
            sha = D._sha256(source)
        except Exception:
            pass
        mapping_payload = {
            "version": 1,
            "schema": "contract-mapping/v1",
            "engine": {"name": ENGINE_NAME, "version": __version__, "mode": "offline-restore"},
            "source": {"path": os.path.abspath(source), "sha256": sha,
                       "name": os.path.basename(source), "type": ext.lstrip(".")},
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "entities": _summarize_entities(mapping_records),
            "items": sorted(mapping_records, key=lambda r: (r.get("start", 0), r.get("end", 0))),
        }
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(mapping_payload, f, ensure_ascii=False, indent=2)

    # 8) 写审计日志
    log_path = None
    if write_log:
        log_path = out_path + ".redaction.log"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "source": os.path.abspath(source),
                "output": os.path.abspath(out_path),
                "enabled_types": sorted(enabled_types),
                "min_confidence": min_confidence,
                "min_severity": min_severity,
                "restore_mode": bool(restore_mode),
                "applied": result["applied"],
                "skipped": result["skipped"],
                "mapping": os.path.abspath(mapping_path) if mapping_path else None,
                "items": [
                    {"type": op.type_id, "label": op.label, "value": op.value,
                     "replacement": op.replacement, "location": op.location,
                     "page": op.page, "bbox": op.bbox, "confidence": op.confidence}
                    for op in ops
                ],
            }, ensure_ascii=False, indent=2))
    return {
        "output": out_path,
        "applied": result["applied"],
        "skipped": result["skipped"],
        "log": log_path,
        "mapping": mapping_path,
        "mapping_embedded": False,
        "restore_mode": bool(restore_mode),
    }


def _load_doc(path: str) -> Document:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return extract_docx(path)
    if ext == ".pdf":
        return extract_pdf(path)
    return extract_text_file(path)


# --------------------------------------------------- 本地 HTTP 服务（供复核页调用）


def start_serve(host: str, port: int, doc_root: str) -> ThreadingHTTPServer:
    """启动一个 127.0.0.1 本地服务，让复核页可一键调用 redactor。

    POST /apply  body = {"source":..., "enabled_types":[...]}
    返 {"ok": True, "output":..., "applied":..., "skipped":..., "download":...}
    """

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            sys.stderr.write("[serve] " + (format % args) + "\n")

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                req = json.loads(body) if body else {}
            except Exception as e:
                self._json(400, {"ok": False, "error": "invalid json: " + str(e)})
                return
            if self.path == "/apply":
                self._apply(req)
            elif self.path == "/health":
                self._json(200, {"ok": True, "service": ENGINE_NAME,
                                 "version": __version__})
            else:
                self._json(404, {"ok": False, "error": "unknown path"})

        def _apply(self, req: Dict[str, Any]):
            src = req.get("source")
            if not src or not os.path.exists(src):
                self._json(400, {"ok": False, "error": f"源文件不存在：{src}"})
                return
            try:
                r = redact_file(
                    source=src,
                    selection={"enabled_types": req.get("enabled_types", [])},
                    min_confidence=float(req.get("min_confidence", 0.5)),
                    min_severity=req.get("min_severity", "low"),
                    out_path=os.path.join(doc_root, _out_name(src)),
                )
                out = r["output"]
                self._json(200, {
                    "ok": True,
                    "output": os.path.basename(out),
                    "applied": r["applied"],
                    "skipped": r["skipped"],
                    "download": "file://" + os.path.abspath(out),
                })
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})

        def do_GET(self):
            if self.path == "/health":
                self._json(200, {"ok": True, "service": ENGINE_NAME,
                                 "version": __version__})
                return
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    f"{ENGINE_NAME} v{__version__}\nPOST /apply  执行脱敏\nGET/POST /health 心跳\n".encode())
            else:
                self._json(404, {"ok": False, "error": "GET not supported"})

        def _json(self, code: int, body: Dict[str, Any]) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer((host, port), Handler)
    return server


def _out_name(src: str) -> str:
    base = os.path.basename(src)
    stem, ext = os.path.splitext(base)
    return f"{stem}_脱敏{ext or '.txt'}"


def _restore_name(src: str) -> str:
    """还原产物的命名:把 <stem>_脱敏.docx → <stem>_还原.docx"""
    base = os.path.basename(src)
    stem, ext = os.path.splitext(base)
    if stem.endswith("_脱敏"):
        stem = stem[:-3]
    return f"{stem}_还原{ext or '.txt'}"


def placeholder_value(label: str, counter: int) -> str:
    """生成与 detector write_mapping 完全一致的占位符。

    形如 "[自然人姓名#1]"。格式只在 detector.placeholder_text 定义一次，
    这里直接委托，避免两处各写一份格式字符串而走样。
    """
    return D.placeholder_text(label, counter)


def _summarize_entities(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 (type, 占位符) 汇总「这份合同一共涉及几种主体、各自出现几次」。"""
    agg: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in records:
        ph = r.get("placeholder") or ""
        parsed = D.parse_placeholder(ph)
        if not parsed:
            continue
        key = (r.get("type", ""), ph)
        item = agg.get(key)
        if item is None:
            agg[key] = {
                "type": r.get("type", ""),
                "label": r.get("label", ""),
                "number": parsed[1],
                "placeholder": ph,
                "original": r.get("original", ""),
                "occurrences": 1,
            }
        else:
            item["occurrences"] += 1
    return sorted(agg.values(), key=lambda x: (x["type"], x["number"]))


# ---------------------------------------------- DOCX 占位符回填（还原） --------


class DocxRestorer:
    """docx 还原器：用 mapping.json 把 [label#N] 占位符回填成原文。

    关键不变式
    ----------
    * 只修改 `<w:t>.text`，不修改 `<w:comment>`、`<w:ins>`、`<w:del>` 等节点。
      python-docx 的 save() 也只会序列化我们触碰过的元素，其他部件原样保留。
    * 批注 (`comments.xml`) 通过 run-id 关联文本段；当我们切分 run 来写大段文本，
      run-id 会重新分配。原本的内容锚定不会跨段移动，所以批注位置不变。
    * 修订标记（tracked changes）位于 run 外层 (`<w:ins>/<w:del>` 包住 `<w:r>`)，
      我们在 run 内做字符级回填，修订语义不变。
    * 段落合并/拆分不会发生 —— 只在一个段落内做替换。

    限制
    ----------
    * PDF 还原不支持：栅格化后文本层已清空，无法程序化回填（必须 OCR）。
    """

    W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def __init__(self, source: str, mapping):
        """mapping 支持两种形态：

        * ``{placeholder: original}``            —— 占位符与原文一一对应（常规情况）
        * ``{placeholder: [original, ...]}``     —— 同一占位符对应多个原文（全称/简称同号）
        """
        self.source = source
        seqs: Dict[str, List[str]] = {}
        for ph, val in dict(mapping).items():
            if isinstance(val, (list, tuple)):
                seqs[ph] = [str(x) for x in val] or [""]
            else:
                seqs[ph] = [str(val)]
        self.seqs = seqs
        # 兼容旧接口：单值映射（取该占位符的最后一个原文）
        self.mapping = {ph: v[-1] for ph, v in seqs.items()}

    def restore(self, dst: str) -> Dict[str, Any]:
        from docx_text import DocxText, paragraph_map, replace_ranges
        package = DocxText(self.source)
        pattern = re.compile("|".join(re.escape(p) for p in sorted(self.seqs, key=len, reverse=True)))
        cursor = {}; applied = 0
        for _, paragraph in package.entries:
            text, _ = paragraph_map(paragraph)
            replacements = []
            for match in pattern.finditer(text):
                ph = match.group(); index = cursor.get(ph, 0)
                if index >= len(self.seqs[ph]):
                    raise RuntimeError("占位符数量与映射不一致，不能安全还原")
                replacements.append((match.start(), match.end(), self.seqs[ph][index], ph))
                cursor[ph] = index+1
            applied += replace_ranges(paragraph, replacements)
        package.save(dst)
        return {"applied": applied, "skipped": 0, "missing": [ph for ph in self.seqs if ph not in cursor]}


# --------------------------------------------------- 还原主流程 ----------------


def load_mapping(path: str) -> Dict[str, str]:
    """读取 detector 的 .mapping.json，返回 {placeholder: original} 字典。

    接受 contract-mapping/v1 schema。**同一实体（含全称/简称）共用一个 placeholder**，
    此时这里只保留其中一个原文；需要精确还原请用 `load_mapping_sequences()`。
    """
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    schema = payload.get("schema", "")
    if schema and not schema.startswith("contract-mapping/"):
        raise RuntimeError(f"mapping.json 的 schema 不识别：{schema}")
    out: Dict[str, str] = {}
    for it in payload.get("items", []):
        ph = it.get("placeholder")
        orig = it.get("original")
        if ph and orig is not None:
            out[ph] = orig
    return out


def load_mapping_sequences(path: str) -> Dict[str, List[str]]:
    """返回 ``{placeholder: [原文, 原文, ...]}``，按**在文档中出现的先后**排序。

    同一个实体（如「北京星海智能科技有限公司」与其简称「星海智能」）共用一个
    占位符 ``[组织机构名称#1]``，但该占位符在不同位置要还原成不同的字面文本。
    还原器按文档顺序逐次取用该列表，就能精确还原。
    """
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    schema = payload.get("schema", "")
    if schema and not schema.startswith("contract-mapping/"):
        raise RuntimeError(f"mapping.json 的 schema 不识别：{schema}")

    rows: List[Tuple[int, int, str, str]] = []
    for idx, it in enumerate(payload.get("items", [])):
        ph = it.get("placeholder")
        orig = it.get("original")
        if not ph or orig is None:
            continue
        start = it.get("start")
        if not isinstance(start, int):
            start = idx
        block = it.get("block_index")
        rows.append((start, block if isinstance(block, int) else idx, ph, orig))
    rows.sort(key=lambda r: (r[0], r[1]))

    out: Dict[str, List[str]] = {}
    for _start, _blk, ph, orig in rows:
        out.setdefault(ph, []).append(orig)
    return out


def find_sibling_mapping(redacted_path: str) -> Optional[str]:
    """在同一目录下寻找与 redacted_path 配对的 mapping.json。

    规则（按优先级）：
      - 嵌入版本：见 `_extract_embedded_mapping`（docx 内部 customXml）
      - <name>.mapping.json                （与原文件同名）
      - <stem>.mapping.json                （去后缀后）
      - <name>_mapping.json                （兜底）
    注意：嵌入版只对 .docx 有效，返回的是 mapping 内容而非路径，
    但 restore_file() 会把内容先写到临时文件再读取。
    """
    folder = os.path.dirname(os.path.abspath(redacted_path))
    base = os.path.basename(redacted_path)
    stem, ext = os.path.splitext(base)
    candidates = [
        os.path.join(folder, f"{stem}{ext}.mapping.json"),
        os.path.join(folder, f"{stem}.mapping.json"),
        os.path.join(folder, f"{base}.mapping.json"),
        os.path.join(folder, f"{stem}_mapping.json"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _extract_embedded_mapping(docx_path: str) -> Optional[Dict[str, Any]]:
    """从 docx zip 内的 customXml 抽出我们嵌进去的 mapping.json 内容。"""
    try:
        import zipfile
        with zipfile.ZipFile(docx_path) as z:
            for name in z.namelist():
                if name.endswith(".mapping.json") or name == "customXml/mapping.json":
                    with z.open(name) as f:
                        return json.loads(f.read().decode("utf-8"))
    except Exception:
        return None
    return None


def embed_mapping_in_docx(docx_path: str, mapping: Dict[str, Any]) -> bool:
    """把 mapping 内容写进 docx zip 的 customXml/mapping.json。

    同时在 [Content_Types].xml 加 override、word/_rels/document.xml.rels 加一个
    relationship，确保 WPS / Word 不会报「未声明的内容类型」警告。

    返回 True 表示成功，False 表示失败（已容错：不影响脱敏产物本身）。
    """
    import zipfile

    target_part = "customXml/mapping.json"
    rel_id = "rIdMapping1"
    ctype = "application/json"
    rels_target = "customXml/mapping.json"

    try:
        with zipfile.ZipFile(docx_path, "r") as zin:
            names = zin.namelist()
            payload_data = json.dumps(mapping, ensure_ascii=False, indent=2).encode("utf-8")
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
                for n in names:
                    if n == target_part:
                        continue
                    data = zin.read(n)
                    if n == "[Content_Types].xml":
                        s = data.decode("utf-8")
                        # 仅当 override 不存在时追加
                        if f'PartName="/{target_part}"' not in s:
                            injection = f'<Override PartName="/{target_part}" ContentType="{ctype}"/>'
                            s = s.replace("</Types>", injection + "</Types>")
                        data = s.encode("utf-8")
                    elif n == "word/_rels/document.xml.rels":
                        s = data.decode("utf-8")
                        if f'Target="{rels_target}"' not in s and f'Id="{rel_id}"' not in s:
                            injection = (
                                f'<Relationship Id="{rel_id}" '
                                f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml" '
                                f'Target="../{rels_target}"/>'
                            )
                            s = s.replace("</Relationships>", injection + "</Relationships>")
                        data = s.encode("utf-8")
                    zout.writestr(n, data)
                # 写我们的 customXml 部件
                zout.writestr(target_part, payload_data)
        with open(docx_path, "wb") as f:
            f.write(buf.getvalue())
        return True
    except Exception as e:
        sys.stderr.write(f"[embed_mapping_in_docx] 失败: {e}\n")
        return False


def restore_file(source: str,
                 mapping_path: Optional[str] = None,
                 out_path: Optional[str] = None,
                 write_log: bool = True) -> Dict[str, Any]:
    """把脱敏后的 docx 还原回原始 docx。

    source: 脱敏后文件路径（docx / pdf —— 仅 docx 真正支持）
    mapping_path: mapping.json 路径；
                  缺省时按 (1) docx 内嵌 customXml、(2) 同目录兄弟文件 顺序查找
    """
    if not os.path.exists(source):
        raise FileNotFoundError(source)

    ext = os.path.splitext(source)[1].lower()
    if ext == ".pdf":
        raise RuntimeError(
            "PDF 已被栅格化（文本层已清），无法程序化还原。"
            "如需还原，请使用 docx 版合同，或使用「脱敏（占位符模式）」+ 保留 docx 源文件。"
        )
    if ext != ".docx":
        raise RuntimeError(f"暂不支持 {ext} 文件的还原；目前只支持 .docx")

    # 1) 优先看 docx 内部嵌的 mapping
    if not mapping_path:
        embedded = _extract_embedded_mapping(source)
        if embedded:
            tmp = source + ".embedded-mapping.json"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(embedded, f, ensure_ascii=False, indent=2)
                mapping_path = tmp
            except Exception:
                mapping_path = None
    # 2) 否则按 sibling 查找
    if not mapping_path:
        mapping_path = find_sibling_mapping(source)
    if not mapping_path or not os.path.exists(mapping_path):
        raise FileNotFoundError(
            f"找不到 mapping.json；请把 mapping 文件路径传入或放在 {source} 同目录。"
        )

    mapping = load_mapping_sequences(mapping_path)
    if not mapping:
        raise RuntimeError(f"mapping.json 内无占位符项：{mapping_path}")

    if not out_path:
        out_path = os.path.join(os.path.dirname(source) or ".",
                                _restore_name(source))

    restorer = DocxRestorer(source, mapping)
    result = restorer.restore(out_path)

    log_path = None
    if write_log:
        log_path = out_path + ".restore.log"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump({
                "source": os.path.abspath(source),
                "output": os.path.abspath(out_path),
                "mapping": os.path.abspath(mapping_path),
                "mapping_source": "embedded" if mapping_path.endswith(".embedded-mapping.json") else "external",
                "applied": result["applied"],
                "missing_placeholders": result.get("missing", []),
                "items": [
                    {"placeholder": ph, "originals": orig}
                    for ph, orig in mapping.items()
                ],
            }, f, ensure_ascii=False, indent=2)

    return {
        "output": out_path,
        "applied": result["applied"],
        "skipped": result["skipped"],
        "missing": result.get("missing", []),
        "log": log_path,
    }


# ---------------------------------------------- 占位符模式脱敏 （嵌入主 redact_file） ------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="contract_redactor.py",
        description="合同脱敏改写器：把识别结果真正写到文件里（docx/pdf/txt）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例：
  python contract_redactor.py 合同.docx --selection 合同.selection.json
  python contract_redactor.py 合同.pdf --types ID_CARD,PHONE_MOBILE,PERSON_NAME
  python contract_redactor.py 合同.docx --types ID_CARD --restore-mode -o 合同_脱敏.docx
  python contract_redactor.py 合同_脱敏.docx --restore --mapping 合同_脱敏.docx.mapping.json
  python contract_redactor.py --serve --port 8765   # 让复核页一键调用
  python contract_redactor.py --app --port 8765     # 起完整的上传/复核/还原 Web 应用
""")
    ap.add_argument("input", nargs="?", help="待脱敏 / 待还原的文件（docx/pdf/txt）")
    ap.add_argument("--selection", help="detector 复核页导出的 selection.json")
    ap.add_argument("--report", help="detector 输出的 .sensitive.json（默认自动找同目录同名报告）")
    ap.add_argument("--types", help="直接指定要脱敏的类型，逗号分隔")
    ap.add_argument("--rules", help="脱敏规则清单 Markdown")
    ap.add_argument("--allowlist", help="白名单文件")
    ap.add_argument("--out", help="输出文件路径（默认原目录 <原名>_脱敏.<ext> 或 _还原.<ext>）")
    ap.add_argument("--min-confidence", type=float, default=0.5)
    ap.add_argument("--min-severity", default="low", choices=["low", "medium", "high"])
    ap.add_argument("--no-log", action="store_true", help="不写 .redaction.log")
    ap.add_argument("--allow-network", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="改写器内置自检")
    ap.add_argument("--serve", action="store_true", help="起 127.0.0.1 本地服务（兼容旧版）")
    ap.add_argument("--app", action="store_true", help="起 上传 / 复核 / 还原 Web 应用")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--doc-root", default=".", help="serve 模式下输出文件所在目录")
    ap.add_argument("--app-workdir", default=None,
                    help="应用模式下的会话工作目录（默认 ./contract_app_sessions）")
    ap.add_argument("--export-mode", choices=["external"], default="external", help="脱敏文件与还原 JSON 分开保存")
    ap.add_argument("--restore-mode", action="store_true",
                    help="脱敏时使用 [label#N] 占位符，并写出 mapping.json 以便还原")
    ap.add_argument("--restore", action="store_true",
                    help="把已脱敏的 docx 通过 mapping.json 还原回原文")
    ap.add_argument("--mapping", help="还原模式下使用的 mapping.json（默认自动按文件名匹配）")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args(argv)

    if not args.allow_network:
        # 服务 / 应用模式需要绑定 TCP 端口，自动开闸；其它情况仍默认离线
        if not (args.serve or args.app):
            D.enforce_offline()

    if args.selftest:
        return redactor_selftest()

    if args.app:
        from contract_app_server import start_app_server
        D.enforce_loopback_only()
        workdir = args.app_workdir or os.path.abspath("./contract_app_sessions")
        srv = start_app_server(args.host, args.port, workdir)
        sys.stderr.write(
            f"[app] Contract Redactor 应用模式 → http://{args.host}:{args.port}\n"
            f"[app] 会话目录：{workdir}\n"
            "[app] 浏览器若没自动打开，请手动访问上方的链接。Ctrl-C 退出。\n"
        )
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            sys.stderr.write("[app] shutting down...\n")
        return 0

    if args.serve:
        raise RuntimeError("旧版服务入口已停用，请使用 contract_app_server.py")
    if not args.input:
        ap.print_help()
        return 2

    # --- 还原分支 ---
    if args.restore:
        try:
            r = restore_file(
                source=args.input,
                mapping_path=args.mapping,
                out_path=args.out,
            )
        except Exception as e:
            print(f"[错误] 还原失败：{e}", file=sys.stderr)
            return 1
        print(f"\n■ 还原完成 → {r['output']}")
        print(f"   替换 {r['applied']} 处")
        if r.get("missing"):
            print(f"   ⚠ {len(r['missing'])} 个占位符未在文档中找到（mapping 比文档更全）")
        if r["log"]:
            print(f"   审计日志 → {r['log']}")
        return 0

    allowlist = load_allowlist(args.allowlist)

    selection = None
    if args.selection:
        selection = load_selection(args.selection)

    types = None
    if args.types:
        types = [t.strip() for t in args.types.split(",") if t.strip()]

    try:
        r = redact_file(
            source=args.input,
            selection=selection,
            types=types,
            out_path=args.out,
            rules_path=args.rules,
            min_confidence=args.min_confidence,
            min_severity=args.min_severity,
            allowlist=list(allowlist),
            write_log=not args.no_log,
            restore_mode=args.restore_mode,
            export_mode=args.export_mode,
        )
    except Exception as e:
        print(f"[错误] 改写失败：{e}", file=sys.stderr)
        return 1

    print(f"\n■ 脱敏完成 → {r['output']}")
    print(f"   替换 {r['applied']} 处，跳过 {r['skipped']} 处")
    if r["log"]:
        print(f"   审计日志 → {r['log']}")
    if r.get("mapping"):
        print(f"   映射文件 → {r['mapping']}  （占位符 ↔ 原文，支持 --restore 还原）")
    return 0


def redactor_selftest() -> int:
    """内置自检：构造一个临时 txt + 几个 ops，跑 apply_to_text 验证。"""
    text = "甲方张三，手机 13812345678，身份证 440305199001012347，住北京市海淀区中关村南大街5号。\n" \
           "金额：人民币 1,280,000.00 元。\n"
    ops = [
        RedactOp(start=text.index("张三"), end=text.index("张三") + 2,
                 type_id="PERSON_NAME", label="姓名", severity="high", confidence=0.9,
                 value="张三", replacement="张**", location="L1"),
        RedactOp(start=text.index("13812345678"), end=text.index("13812345678") + 11,
                 type_id="PHONE_MOBILE", label="手机", severity="high", confidence=0.95,
                 value="13812345678", replacement="138****5678", location="L1"),
        RedactOp(start=text.index("440305199001012347"),
                 end=text.index("440305199001012347") + 18,
                 type_id="ID_CARD", label="身份证", severity="high", confidence=0.99,
                 value="440305199001012347", replacement="440305********2347", location="L1"),
    ]
    red = TextRedactor("<selftest>", text, ops)
    out, applied, skipped = red.apply_to_text(text)
    fails = []
    if "张**" not in out: fails.append("姓名未脱敏")
    if "138****5678" not in out: fails.append("手机号未脱敏")
    if "440305********2347" not in out: fails.append("身份证未脱敏")
    if applied != 3: fails.append(f"applied={applied} (应为 3)")
    print("== 改写器自检 ==")
    if fails:
        for f in fails: print("  [FAIL]", f)
        return 1
    print("  [PASS] 文本改写正确（applied=3, skipped=0）")
    print(f"  原文 → 脱敏后：\n  {out.strip()[:120]}…")
    return 0




# TYPE_META is shared by the legacy detectors; prevent concurrent rule mutation.
def _locked_redact(function):
    from functools import wraps
    @wraps(function)
    def call(*args, **kwargs):
        with D.RULES_LOCK:
            return function(*args, **kwargs)
    return call
redact_file = _locked_redact(redact_file)

if __name__ == "__main__":
    sys.exit(main())
