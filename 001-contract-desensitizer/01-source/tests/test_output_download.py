#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回归测试：确认脱敏后的「保存」链路。

覆盖三件事：
  1) 复核页默认就把 docx + mapping.json 一起存（optJson 默认勾选，可取消）；
     且有「选择保存文件夹」入口，前端脚本语法必须能被 JS 引擎解析。
  2) mapping.json 必须真的能下载到（用户反馈「没有保存 mapping」）。
  3) 复核页里被用户点掉的单个位置，产物里必须真的没有被替换
     （否则预览与实际不一致，用户会以为选错了）。

用法：python tests/test_output_download.py
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import contract_app_server as S  # noqa: E402
from docx import Document  # noqa: E402

C01 = ("/Users/agent/Downloads/Contract_Copilot_全部实测用例与问题汇总_20260831/"
       "02_测试材料/C01/input.docx")

fails = []


def check(name, cond, detail=""):
    if not cond:
        fails.append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def upload(base, path, filename=None):
    b = "----wb" + uuid.uuid4().hex
    data = open(path, "rb").read()
    body = io.BytesIO()
    body.write(f'--{b}\r\nContent-Disposition: form-data; name="mode"\r\n\r\nredact\r\n'.encode())
    body.write(
        f'--{b}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename or os.path.basename(path)}"\r\n'
        f'Content-Type: application/octet-stream\r\n\r\n'.encode())
    body.write(data + b"\r\n" + f"--{b}--\r\n".encode())
    req = urllib.request.Request(
        base + "/api/upload", data=body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={b}"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=600).read())


def get(base, p):
    return urllib.request.urlopen(base + p, timeout=600).read()


def post(base, p, payload):
    req = urllib.request.Request(
        base + p, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=900).read())


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        xml = "".join(z.read(n).decode("utf-8") for n in z.namelist()
                      if n.startswith("word/") and n.endswith(".xml"))
    return "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S))


def kept_sample(rv, mark):
    """按全局偏移从复核页 payload 里取出被点掉那处的原文字样。"""
    for b in rv["blocks"]:
        s = b["start"]
        if s <= mark["s"] and mark["e"] <= s + len(b["text"]):
            return b["text"][mark["s"] - s: mark["e"] - s]
    return ""


def main():
    if not os.path.exists(C01):
        print(f"跳过：找不到样例 {C01}")
        return 0

    tmp = tempfile.mkdtemp(prefix="out_dl_")
    src = os.path.join(tmp, "input.docx")
    shutil.copyfile(C01, src)
    host, port = "127.0.0.1", 18893
    base = f"http://{host}:{port}"
    srv = S.start_app_server(host, port, os.path.join(tmp, "sessions"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.4)

    try:
        up = upload(base, src)
        sid = up["sid"]

        # ---------------------------------------------------- 1) 复核页控件
        print("== 1. 复核页的保存选项 ==")
        html = get(base, f"/review?sid={sid}").decode("utf-8")
        check("有 mapping.json 勾选项且默认勾选",
              re.search(r'id="optJson"[^>]*checked', html) is not None)
        check("docx 为必选项（勾选且禁用）",
              re.search(r'id="optDoc"[^>]*checked[^>]*disabled', html) is not None)
        check("有「选择保存文件夹」按钮", 'id="pickDir"' in html)
        check("提示保存到浏览器默认目录", "浏览器默认下载目录" in html)

        # 前端脚本语法必须合法（浏览器才能跑）
        scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
        js = "\n".join(scripts)
        with open(os.path.join(tmp, "review.js"), "w", encoding="utf-8") as f:
            f.write(js)
        node = None
        for cand in ("/Users/agent/.workbuddy/binaries/node/versions/22.22.2-2/bin/node",
                     "/opt/homebrew/bin/node"):
            if os.path.exists(cand):
                node = cand
                break
        if node:
            rc = os.system(f'"{node}" --check "{tmp}/review.js" > "{tmp}/node.log" 2>&1')
            check("页面 JS 语法检查通过", rc == 0,
                  open(os.path.join(tmp, "node.log")).read().strip()[:200])
        else:
            check("页面 JS 语法检查通过", False, "找不到 node")

        # ---------------------------------------------------- 2) mapping 可下载
        print("\n== 2. docx + mapping.json 都要能下载 ==")
        ap = post(base, f"/api/apply/{sid}", {"enabled_types": []})
        check("apply 返回 output_url / mapping_url",
              bool(ap.get("output_url")) and bool(ap.get("mapping_url")),
              f"applied={ap.get('applied')} mapping={ap.get('mapping_name')}")
        out_blob = get(base, ap["output_url"])
        mp_blob = get(base, ap["mapping_url"])
        check("脱敏 docx 可下载且是 zip", out_blob[:2] == b"PK" and len(out_blob) > 10000,
              f"{len(out_blob)} bytes")
        check("mapping.json 可下载且是 JSON", mp_blob.lstrip()[:1] == b"{",
              f"{len(mp_blob)} bytes")
        mp = json.loads(mp_blob.decode("utf-8"))
        check("mapping schema 正确", str(mp.get("schema", "")).startswith("contract-mapping/"))

        # mapping 与产物必须对得上：占位符集合一致
        text = docx_text(io.BytesIO(out_blob))
        ph_doc = set(re.findall(r"\[[^\[\]#]{1,12}#\d+\]", text))
        ph_map = {it["placeholder"] for it in mp.get("items", [])}
        check("产物里的占位符 ⊆ mapping 覆盖范围", ph_doc <= ph_map,
              f"产物 {len(ph_doc)} 种 / mapping {len(ph_map)} 种")

        # ---------------------------------------------------- 3) 取消单个位置
        print("\n== 3. 复核页点掉的位置必须真的不替换 ==")
        m = re.search(r"var DATA = (\{.*?\});\n", html, re.S)
        rv = json.loads(m.group(1))
        name_marks = []
        for bi, blk in enumerate(rv["blocks"]):
            for mk in blk.get("marks", []):
                if mk["t"] == "PERSON_NAME":
                    name_marks.append((bi, mk))
        if len(name_marks) >= 2:
            # 只保留第 1 个姓名位置，其余全部点掉
            items = [{"type": name_marks[0][1]["t"],
                      "offset": [name_marks[0][1]["s"], name_marks[0][1]["e"]]}]
            ap2 = post(base, f"/api/apply/{sid}",
                       {"enabled_types": ["PERSON_NAME"], "items": items})
            out2 = get(base, ap2["output_url"])
            t2 = docx_text(io.BytesIO(out2))
            got = len(re.findall(r"\[自然人姓名#\d+\]", t2))
            check("只保留 1 处姓名 → 产物只替换 1 处", got == 1,
                  f"实际替换 {got} 处（applied={ap2['applied']}）")
            # 被点掉的位置必须原样保留原文
            dropped = name_marks[1][1]
            sample = kept_sample(rv, dropped)
            check("被点掉的位置仍保留原文字样",
                  bool(sample) and sample in t2, f"原文片段 {sample!r}")
        else:
            check("只保留 1 处姓名 → 产物只替换 1 处", False,
                  f"样例里 PERSON_NAME 位置不足 2 个（{len(name_marks)}）")

    finally:
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fails:
        print(f"✘ 失败 {len(fails)} 项：" + "；".join(fails))
        return 1
    print("✔ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
