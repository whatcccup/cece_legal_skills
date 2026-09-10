#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
contract_app_server.py
======================
合同脱敏 + 还原一体化 Web 应用：本地 HTTP 服务，对外提供：
  - 上传 docx/pdf
  - 自动进入「脱敏前 / 脱敏后」左右对比页（展示全文）
  - 高中低分类筛选项 / 类型多选框
  - 用户点击确认 → 生成 <name>_脱敏.docx + mapping.json
  - 「还原」模式：自动匹配 sibling mapping；缺则让用户上传
  - 还原时**不动**批注 / 审阅 / 修订 / 样式（仅替换 <w:t>.text）

设计思路
--------
* 完全离线：与 detector / redactor 共享 enforce_offline()。
* 会话隔离：每个上传文件一个 session 目录，sid 为 UUID。
* 输出脱敏产品统一为占位符模式（[label#N]） + mapping.json，方便一键还原。
"""
from __future__ import annotations

import html as _html
import io
import json
import os
import re
import sys
import threading
import time
import uuid
import urllib.parse
import shutil
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

# 复用 detector / redactor 的离线算法、改写器、还原器
import contract_sensitive_detector as D
from contract_sensitive_detector import (
    TYPE_META,
    Settings,
    DetectorEngine,
    load_rules_md,
    load_document,
    build_report,
    write_mapping,
)
from contract_redactor import (
    ENGINE_NAME as REDACTOR_NAME,
    __version__ as REDACTOR_VERSION,
    redact_file,
    restore_file,
    find_sibling_mapping,
    _extract_embedded_mapping,
)


APP_NAME = "contract_app_server"
APP_VERSION = "1.1.0"
DEFAULT_PORT = 18800
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


# ---------------------------------------------------------------- HTML / UI --
# 所有页面模板（CSS / HTML / JS）集中在 contract_app_ui.py，便于单独调整设计，
# 不触碰服务端处理逻辑。此处只做转发。
from contract_app_ui import (          # noqa: E402
    build_upload_page,
    build_workspace_body,
    build_review_page,
    build_expired_page,
    loading_doc,
    FAVICON_SVG,
)


# --------------------------------------------------------------- 服务端状态 ----


class AppState:
    """会话状态：每个上传文件一个 sid，对应一个工作目录。"""

    def __init__(self, work_dir: str):
        os.makedirs(work_dir, exist_ok=True)
        self.work_dir = work_dir
        self.uploads: Dict[str, Dict[str, Any]] = {}

    def new_session(self, sid: str, info: Dict[str, Any]) -> None:
        self.uploads[sid] = info

    def get(self, sid: str) -> Optional[Dict[str, Any]]:
        return self.uploads.get(sid)


# --------------------------------------------------------------- 工具函数 ------


def _safe_filename(name: str) -> str:
    """剥离路径成分，并只允许简单的 ascii + 中日韩。"""
    base = os.path.basename(name or "upload.bin")
    base = re.sub(r"[\\/]+", "_", base)
    return base or "upload.bin"


def _ext_of(name: str) -> str:
    return os.path.splitext(name)[1].lower()


def _run_detector(path: str) -> Dict[str, Any]:
    """对刚上传的路径跑一次 detector，返回 (doc, candidates, report, report_full_text)。

    使用 detector 默认配置 + 项目同目录的 rules markdown。
    """
    rules_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "脱敏规则清单.md",
    )
    extra_specs: List = []
    if os.path.exists(rules_path):
        try:
            extra_specs = load_rules_md(rules_path)
        except Exception:
            extra_specs = []
    settings = Settings(min_confidence=0.5, min_severity="low")
    if extra_specs:
        from contract_sensitive_detector import TYPE_META as _TM, TypeMeta
        import dataclasses as _dc
        for s in extra_specs:
            if s.type_id in _TM:
                cur = _TM[s.type_id]
                kw = {}
                if getattr(s, "severity", None):
                    kw["severity"] = s.severity
                if getattr(s, "enabled", None) is False:
                    settings.disabled.add(s.type_id)
                if kw:
                    _TM[s.type_id] = _dc.replace(cur, **kw)
    engine = DetectorEngine(settings)
    doc = load_document(path, include_headers=True)
    candidates = engine.scan_document(doc)
    report = build_report(doc, candidates, settings)
    full_raw = "\n".join(b.text.rstrip("\n") for b in doc.blocks)
    return {
        "doc": doc, "candidates": candidates, "report": report,
        "full_raw": full_raw,
    }


def _looks_like_redacted(redacted_path: str) -> bool:
    """粗略判断文件是否已经是脱敏产物（占位符 [label#N] 出现）。"""
    PLACEHOLDER_PATTERN = re.compile(r"\[[^\]\[]{1,16}#\d+\]")
    ext = _ext_of(redacted_path)
    try:
        if ext == ".docx":
            import zipfile
            with zipfile.ZipFile(redacted_path) as z:
                names = [n for n in z.namelist() if n.startswith("word/") and n.endswith(".xml")]
                for n in names[:8]:
                    with z.open(n) as f:
                        chunk = f.read(200_000).decode("utf-8", errors="ignore")
                    if PLACEHOLDER_PATTERN.search(chunk):
                        return True
            return False
        if ext in (".txt", ".md"):
            with open(redacted_path, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(200_000)
            return bool(PLACEHOLDER_PATTERN.search(head))
    except Exception:
        return False
    return False


# 页面渲染统一委托给 contract_app_ui（见文件头部 import）。


# --------------------------------------------------------------- HTTP handler --


class AppHandler(BaseHTTPRequestHandler):
    state: AppState = None  # injected by start_app_server

    # 关闭 socket 时的额外日志噪音
    def log_message(self, fmt, *args):
        sys.stderr.write("[app] " + (fmt % args) + "\n")

    def _send(self, code: int, content_type: str, body: bytes,
              extra_headers: Optional[List[Tuple[str, str]]] = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj: Any, code: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, "application/json; charset=utf-8", data)

    def _send_html(self, body, code: int = 200) -> None:
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._send(code, "text/html; charset=utf-8", body)

    # ---- GET ----
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        qs = urllib.parse.parse_qs(u.query)
        sid = (qs.get("sid") or [""])[0]

        if path == "/" or path == "/index.html":
            self._send_html(build_upload_page())
            return
        if path == "/loading" or path == "/loading.html":
            self._send_html(loading_doc())
            return
        if path in ("/favicon.svg", "/favicon.ico"):
            self._send(200, "image/svg+xml; charset=utf-8", FAVICON_SVG.encode("utf-8"))
            return
        if path == "/health":
            self._send_json({"ok": True, "service": APP_NAME, "version": APP_VERSION})
            return
        if path.startswith("/download/"):
            # /download/<sid>/<encoded-name...>
            # 文件实际位置：<workdir>/<sid>/out/<name>（与 /api/apply 一致）
            parts = path.split("/")
            if len(parts) < 4:
                self._send_json({"ok": False, "error": "bad download path"}, 400)
                return
            dsid = parts[2]
            name = "/".join(parts[3:])
            name = urllib.parse.unquote(name)
            info = self.state.get(dsid)
            if not info:
                self._send_json({"ok": False, "error": "session not found"}, 404)
                return
            target = os.path.abspath(os.path.join(self.state.work_dir, dsid, "out", name))
            safe_root = os.path.abspath(os.path.join(self.state.work_dir, dsid, "out")) + os.sep
            if not (target + os.sep).startswith(safe_root):
                self._send_json({"ok": False, "error": "bad path"}, 400)
                return
            if not os.path.exists(target):
                self._send_json({"ok": False, "error": "file not found"}, 404)
                return
            with open(target, "rb") as f:
                data = f.read()
            ctype = "application/octet-stream"
            ext = os.path.splitext(target)[1].lower()
            if ext == ".docx":
                ctype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif ext == ".json":
                ctype = "application/json; charset=utf-8"
            elif ext == ".log":
                ctype = "text/plain; charset=utf-8"
            disp = f'attachment; filename="{urllib.parse.quote(os.path.basename(target))}"'
            self._send(200, ctype, data, [("Content-Disposition", disp)])
            return
        if path == "/workspace":
            info = self.state.get(sid)
            if not info:
                self._send_html(build_expired_page())
                return
            self._send_html(build_workspace_body(sid, info))
            return
        if path == "/review":
            info = self.state.get(sid)
            if not info:
                self._send_html(build_expired_page())
                return
            self._send_html(build_review_page(sid, info))
            return

        self._send_json({"ok": False, "error": "GET not found"}, 404)

    # ---- POST ----
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        ctype = self.headers.get("Content-Type", "")
        body_bytes = b""
        clen = int(self.headers.get("Content-Length", "0") or 0)
        if clen:
            body_bytes = self.rfile.read(clen)

        # 解析 multipart
        def parse_multipart():
            """最简单的 multipart 解析，返回 {field_name: {filename, content_type, data}}"""
            if not ctype.startswith("multipart/form-data"):
                return {}
            m = re.match(r'multipart/form-data;\s*boundary=(.*)', ctype)
            if not m:
                return {}
            boundary = b"--" + m.group(1).encode("ascii")
            out: Dict[str, Dict[str, Any]] = {}
            parts = body_bytes.split(boundary)
            for p in parts[1:-1]:
                if p.startswith(b"\r\n"):
                    p = p[2:]
                if p.endswith(b"\r\n"):
                    p = p[:-2]
                if not p:
                    continue
                head_blob, _, data = p.partition(b"\r\n\r\n")
                head = head_blob.decode("utf-8", errors="ignore")
                # 解析 Content-Disposition
                name_m = re.search(r'name="([^"]+)"', head)
                filename_m = re.search(r'filename="([^"]*)"', head)
                ctype_m = re.search(r'Content-Type:\s*(.+)', head)
                if not name_m:
                    continue
                name = name_m.group(1)
                filename = filename_m.group(1) if filename_m else ""
                content_type = (ctype_m.group(1).strip() if ctype_m else "")
                out[name] = {
                    "filename": filename,
                    "content_type": content_type,
                    "data": data,
                }
            return out

        # --- 路由 ---
        if path == "/api/shutdown":
            # 供网页右上角「退出」按钮调用：优雅停止本地服务并释放端口
            self._send_json({"ok": True, "message": "shutting down"})
            _srv = self.server

            def _stop() -> None:
                time.sleep(0.25)          # 先让 HTTP 响应写出去
                try:
                    _srv.shutdown()
                except Exception:
                    pass
                try:
                    _srv.server_close()
                except Exception:
                    pass
                time.sleep(0.2)
                os._exit(0)               # 确保端口一定被释放

            try:
                threading.Thread(target=_stop, daemon=True).start()
            except Exception as exc:      # 不应发生；退化为直接退出
                sys.stderr.write(f"[app] shutdown failed: {exc}\n")
                os._exit(0)
            return

        if path == "/api/upload":
            try:
                mp = parse_multipart()
                fld = mp.get("file")
                mode = (mp.get("mode", {}).get("data") or b"redact").decode("utf-8").strip().lower()
                if mode not in ("redact", "restore"):
                    mode = "redact"
                if not fld or not fld.get("data"):
                    self._send_json({"ok": False, "error": "未选择文件"}, 400)
                    return
                if len(fld["data"]) > MAX_UPLOAD_BYTES:
                    self._send_json(
                        {"ok": False, "error": f"文件超过 {MAX_UPLOAD_BYTES//1024//1024} MB 上限"},
                        413)
                    return
                safe_name = _safe_filename(fld.get("filename") or "upload.bin")
                sid = uuid.uuid4().hex[:12]
                sess_dir = os.path.join(self.state.work_dir, sid)
                os.makedirs(sess_dir, exist_ok=True)
                input_path = os.path.join(sess_dir, safe_name)
                with open(input_path, "wb") as f:
                    f.write(fld["data"])
                ext = _ext_of(input_path)
                if ext not in (".docx", ".pdf", ".txt", ".md"):
                    try:
                        os.remove(input_path)
                    except Exception:
                        pass
                    self._send_json({"ok": False, "error": f"暂不支持 {ext} 文件"}, 400)
                    return

                # 检测文件是否已含占位符
                is_redacted = _looks_like_redacted(input_path)

                if mode == "restore":
                    # 还原模式：跳过 detector。直接找 sibling mapping 和内嵌 mapping。
                    sib_mapping = find_sibling_mapping(input_path)
                    has_embedded = False
                    try:
                        if _extract_embedded_mapping(input_path) is not None:
                            has_embedded = True
                    except Exception:
                        pass
                    # 选择首个可用；如果两个都有，优先 sibling（更直观）
                    chosen = sib_mapping if (sib_mapping and os.path.exists(sib_mapping)) else (
                        "embedded" if has_embedded else None)
                    info = {
                        "sid": sid,
                        "filename": safe_name,
                        "input_path": input_path,
                        "mode": "restore",
                        "is_redacted": is_redacted,
                        "sibling_mapping": sib_mapping,
                        "mapping_path": chosen,
                        "has_embedded_mapping": has_embedded,
                        "outputs": {},
                    }
                    self.state.new_session(sid, info)
                    self._send_json({
                        "ok": True, "sid": sid,
                        "filename": safe_name, "mode": "restore",
                        "looks_redacted": is_redacted,
                        "mapping_found": bool(chosen),
                        "mapping_source": "embedded" if chosen == "embedded" else "file" if chosen else None,
                        "redirect": f"/workspace?sid={sid}",
                    })
                    return

                # ---- redact mode ----
                run = _run_detector(input_path)
                report = run["report"]
                doc = run["doc"]
                full_raw = run["full_raw"]

                # 写 mapping.json （它就是后续还原器要用的）
                mapping_path = os.path.join(sess_dir, safe_name + ".mapping.json")
                write_mapping(report, mapping_path)

                # 构造 review payload
                review_payload = _build_review_payload(report, doc.blocks)

                # 找 sibling mapping（detector 模式下不会用到，先留着）
                sib_mapping = find_sibling_mapping(input_path) or mapping_path

                info = {
                    "sid": sid,
                    "filename": safe_name,
                    "input_path": input_path,
                    "mode": "redact",
                    "report": report,
                    "doc": doc,
                    "full_raw": full_raw,
                    "review_payload": review_payload,
                    "mapping_path": mapping_path,
                    "sibling_mapping": sib_mapping,
                    "looks_redacted": is_redacted,
                    "counts": {"types": len(report["items"]),
                               "occurrences": report["summary"]["occurrences"]},
                    "outputs": {},
                }
                self.state.new_session(sid, info)
                self._send_json({
                    "ok": True, "sid": sid,
                    "filename": safe_name, "mode": "redact",
                    "counts": info["counts"],
                    "looks_redacted": is_redacted,
                    "mapping_found": os.path.exists(sib_mapping),
                    "redirect": f"/workspace?sid={sid}",
                })
            except Exception as exc:
                self._send_json({"ok": False, "error": f"上传/识别失败：{exc}"}, 500)
            return

        # ---------------- /api/apply/<sid> ----------------
        m = re.match(r"^/api/apply/([A-Za-z0-9_-]+)$", path)
        if m:
            sid = m.group(1)
            info = self.state.get(sid)
            if not info:
                self._send_json({"ok": False, "error": "session not found"}, 404)
                return
            try:
                req = json.loads(body_bytes.decode("utf-8") or "{}")
            except Exception:
                self._send_json({"ok": False, "error": "invalid json"}, 400)
                return
            input_path = info["input_path"]
            ext = _ext_of(input_path)

            # 决定输出目录 / 路径
            out_dir = os.path.join(self.state.work_dir, sid, "out")
            os.makedirs(out_dir, exist_ok=True)
            stem = os.path.splitext(os.path.basename(input_path))[0]
            output_name = f"{stem}_脱敏{ext or '.txt'}"
            out_path = os.path.join(out_dir, output_name)

            enabled_types = req.get("enabled_types") or []
            if isinstance(enabled_types, str):
                enabled_types = [t.strip() for t in enabled_types.split(",") if t.strip()]
            if not enabled_types:
                # 默认全部
                enabled_types = [it["type"] for it in info["report"]["items"]]

            # 复核页逐个位置的勾选（用户在预览里点掉的高亮必须真的不替换）
            enabled_items = req.get("items")
            if not isinstance(enabled_items, list):
                enabled_items = None

            warnings = ""
            try:
                # 注：含占位符的文件 = 已被脱敏过，二次脱敏会再次写出 placeholder
                # 避免重叠加：在该文件下不再生成新的 mapping（直接复用上一次）
                if info.get("looks_redacted") and ext == ".docx":
                    warnings = "⚠ 文件疑似已经过脱敏，将再次覆盖 placeholder。"
                r = redact_file(
                    source=input_path,
                    selection={"enabled_types": enabled_types, "items": enabled_items},
                    out_path=out_path,
                    min_confidence=float(req.get("min_confidence", 0.5)),
                    min_severity=req.get("min_severity", "low"),
                    restore_mode=True,
                )
            except Exception as exc:
                self._send_json({"ok": False, "error": f"脱敏失败：{exc}"}, 500)
                return

            # 把 mapping.json 复制到 out_dir
            # 注意：优先用 redact_file 产出的那份 —— 它只包含本次实际启用的类型，
            # 与刚生成的 <name>_脱敏.docx 里的占位符严格对应（upload 时那份是"全量"，
            # 用户若取消勾选某些类型，两者会对不上）。
            mapping_src = r.get("mapping") or info["mapping_path"]
            mapping_dst = os.path.join(out_dir, output_name + ".mapping.json")
            try:
                import shutil
                shutil.copyfile(mapping_src, mapping_dst)
            except Exception:
                mapping_dst = mapping_src

            # 复制 log
            log_dst = None
            if r.get("log") and os.path.exists(r["log"]):
                log_dst = os.path.join(out_dir, output_name + ".redaction.log")
                try:
                    import shutil
                    shutil.copyfile(r["log"], log_dst)
                except Exception:
                    log_dst = None

            self._send_json({
                "ok": True,
                "output_name": output_name,
                "output_url": f"/download/{sid}/{urllib.parse.quote(output_name)}",
                "mapping_name": os.path.basename(mapping_dst),
                "mapping_url": f"/download/{sid}/{urllib.parse.quote(os.path.basename(mapping_dst))}",
                "log_url": f"/download/{sid}/{urllib.parse.quote(os.path.basename(log_dst))}" if log_dst else None,
                "applied": r["applied"],
                "skipped": r["skipped"],
                "warnings": warnings,
            })
            return

        # ---------------- /api/restore/<sid> ----------------
        m = re.match(r"^/api/restore/([A-Za-z0-9_-]+)$", path)
        if m:
            sid = m.group(1)
            info = self.state.get(sid)
            if not info:
                self._send_json({"ok": False, "error": "session not found"}, 404)
                return

            mapping_path: Optional[str] = None
            restore_kwargs: Dict[str, Any] = {}
            if ctype.startswith("multipart/form-data"):
                mp = parse_multipart()
                if "mapping" in mp:
                    fname = _safe_filename(mp["mapping"].get("filename") or "mapping.json")
                    mp_path = os.path.join(self.state.work_dir, sid, fname)
                    with open(mp_path, "wb") as f:
                        f.write(mp["mapping"]["data"])
                    mapping_path = mp_path
            elif ctype.startswith("application/json"):
                try:
                    req = json.loads(body_bytes.decode("utf-8") or "{}")
                except Exception:
                    self._send_json({"ok": False, "error": "invalid json"}, 400)
                    return
                req_mapping = req.get("mapping")
                if req_mapping:
                    mapping_path = req_mapping
            if not mapping_path:
                # 自动找
                sib = info.get("sibling_mapping") or find_sibling_mapping(info["input_path"])
                if sib and os.path.exists(sib):
                    mapping_path = sib
                # 注：mapping_path 可能为 None —— restore_file() 会自动尝试 docx 内嵌

            input_path = info["input_path"]
            ext = _ext_of(input_path)
            out_dir = os.path.join(self.state.work_dir, sid, "out")
            os.makedirs(out_dir, exist_ok=True)
            stem = os.path.splitext(os.path.basename(input_path))[0]
            output_name = f"{stem}_还原{ext or '.txt'}"
            out_path = os.path.join(out_dir, output_name)

            # 在「脱敏会话」里点还原时，要还原的是**刚生成的脱敏产物**（含占位符），
            # 而不是最初上传的原件 —— 后者本来就没有占位符，还原会变成空操作。
            if info.get("mode") != "restore":
                redacted_candidate = os.path.join(out_dir, f"{stem}_脱敏{ext or '.txt'}")
                if os.path.exists(redacted_candidate):
                    input_path = redacted_candidate

            try:
                r = restore_file(
                    source=input_path,
                    mapping_path=mapping_path,  # None → 自动找内嵌
                    out_path=out_path,
                )
            except FileNotFoundError as exc:
                self._send_json({"ok": False,
                    "error": "找不到 mapping.json —— 请上传一个 (.json)。"}, 400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": f"还原失败：{exc}"}, 500)
                return
            self._send_json({
                "ok": True,
                "output_name": output_name,
                "output_url": f"/download/{sid}/{urllib.parse.quote(output_name)}",
                "applied": r["applied"],
                "skipped": r["skipped"],
                "missing": r.get("missing") or [],
            })
            return

        self._send_json({"ok": False, "error": "POST not found"}, 404)


# --------------------------------------------------------------- 服务启动 ------


def _build_review_payload(report: Dict[str, Any], doc_blocks: List[Any]) -> Dict[str, Any]:
    """构造 /review 页所需的 JSON：每段的全文 + 高亮区间 + 占位符预览。

    与 detector 的 _build_review_payload 类似，但额外保留 occ 的【全 occurrence 索引】
    用于前端精确按 occurrence 控制勾选。
    """
    buckets: Dict[int, List[Dict[str, Any]]] = {}
    types: Dict[str, Dict[str, Any]] = {}
    # 编号必须与 detector.write_mapping / redactor 完全一致：
    # 同一个实体（同一个人/企业，含简称）在整篇里共用同一个 [标签#N]。
    numberer = D.EntityNumberer(report["items"])
    for it in report["items"]:
        t = types.setdefault(it["type"], {
            "id": it["type"], "label": it["label"], "cat": it["category"],
            "sev": it["severity"], "count": 0,
        })
        t["count"] += it["count"]
        placeholder = numberer.placeholder(it["type"], it["value"], it["label"])
        for occ_index, o in enumerate(it["occurrences"]):
            buckets.setdefault(o["block_index"], []).append({
                "s": o["offset"][0], "e": o["offset"][1],
                "t": it["type"], "sev": it["severity"], "label": it["label"],
                "placeholder": placeholder,
                "masked": it["masked"], "conf": it["confidence"],
                "occ_start": occ_index, "occ_end": occ_index + 1,
            })

    # detector extract_* 用 "\n".join(...) 拼接全文，块起点累加方式：
    #   pos = 0;
    #   for b in doc.blocks: blocks.append({"start":pos,...}); pos += len(text)+1
    # 因此我们重建出和 detector 一致的 start 起点
    blocks: List[Dict[str, Any]] = []
    pos = 0
    for b in doc_blocks:
        text = (b.text or "").rstrip("\n")
        blocks.append({
            "start": pos,
            "loc": b.location,
            "text": text,
            "marks": buckets.get(len(blocks), []),
        })
        pos += len(text) + 1

    return {
        "source_path": report.get("source", {}).get("path", ""),
        "min_confidence": report["settings"]["min_confidence"],
        "min_severity": report["settings"].get("min_severity", "low"),
        "warnings": report.get("warnings") or [],
        "types": list(types.values()),
        "blocks": blocks,
    }


def start_app_server(host: str, port: int, work_dir: str) -> ThreadingHTTPServer:
    """启动 Contract Redactor Web 应用。"""
    os.makedirs(work_dir, exist_ok=True)
    state = AppState(work_dir)

    # 修正：review payload 需要 doc.blocks 信息 —— 重写一份带完整文本的版本
    # 这里 monkey-patch 一下 AppHandler 的 POST 处理逻辑（在 do_POST /api/upload 已经有完整 doc，
    # 我们直接构造 payload）。但 _build_review_payload 单独存在是为了 HTML 嵌入。
    # 这里直接升级 do_POST 的构造：覆盖 _build_review_payload 用更完整的信息

    handler_cls = _make_handler(state)
    server = ThreadingHTTPServer((host, port), handler_cls)
    return server


def _make_handler(state: AppState):
    """构造一个绑定了 state 的 Handler 子类。"""
    class _H(AppHandler):
        pass
    _H.state = state
    return _H


# ==============================================================================
# 启动脚本
# ==============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="contract_app_server.py",
        description="合同脱敏 / 还原 一体化 Web 应用（本地 127.0.0.1）",
    )
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--workdir", default="./contract_app_sessions",
                    help="会话工作目录（每个上传文件一个独立子目录）")
    ap.add_argument("--open-browser", action="store_true",
                    help="启动后自动打开主页面（优先使用 Chrome 应用窗口）")
    args = ap.parse_args(argv)

    # 启动期间放开网络（127.0.0.1 绑定 / 可选浏览器跳转）
    D.enforce_offline = lambda: None  # 临时禁掉，避免 start_app 失败

    workdir = os.path.abspath(args.workdir)
    os.makedirs(workdir, exist_ok=True)
    server = start_app_server(args.host, args.port, workdir)
    base = f"http://{args.host}:{args.port}"
    print()
    print("  ┌──────────────────────────────────────────────────────┐")
    print("  │   合同脱敏 / 还原  ·  Contract Redactor                │")
    print("  └──────────────────────────────────────────────────────┘")
    print(f"  ◆ 版本：      v{APP_VERSION}")
    print(f"  ◆ 访问地址：  {base}/")
    print(f"  ◆ 会话目录：  {workdir}")
    print("  ◆ 完全离线：  仅监听 127.0.0.1，不产生任何外联流量")
    print()
    print("  停止服务：网页右上角「退出」，或在此按 Ctrl-C")
    print()
    if args.open_browser:
        import threading, webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{args.host}:{args.port}/")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  shutting down...")
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
