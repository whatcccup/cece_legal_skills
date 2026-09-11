#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合同脱敏助手 · 跨平台启动器（Windows / macOS / Linux 通用）

用法：
    python start.py                 启动本地服务并自动打开浏览器
    python start.py --foreground    前台运行，日志留在当前终端，Ctrl-C 结束

行为：
    1. 找到带依赖的 Python；没有就自动建 .venv 并安装 requirements.txt（仅首次）
    2. 释放 18800 端口、结束上一次的服务进程
    3. 启动 contract_app_server.py（完全离线，只监听 127.0.0.1）
    4. 健康检查通过后打开 http://127.0.0.1:18800/

只依赖标准库，不需要 bash / bat / vbs。
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PORT = int(os.environ.get("REDACTOR_PORT", "18800"))
APP_URL = f"http://127.0.0.1:{PORT}/"
REQUIRED = ("docx", "pdfplumber", "pypdf", "reportlab", "pypdfium2", "PIL")
MIN_PY = (3, 9)


def here() -> Path:
    return Path(__file__).resolve().parent


def project_dir() -> Path:
    return here().parent


def has_deps(python: Path) -> bool:
    code = "import " + ", ".join(REQUIRED)
    try:
        return subprocess.run([str(python), "-c", code],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False


def pick_python(proj: Path) -> Path | None:
    venv_py = proj / ".venv" / ("Scripts" if os.name == "nt" else "bin") / \
        ("python.exe" if os.name == "nt" else "python")
    candidates = [venv_py, Path(sys.executable)]
    found = os.environ.get("PYTHON")
    if found:
        candidates.append(Path(found))
    for c in candidates:
        if c.exists() and has_deps(c):
            return c
    return None


def bootstrap(proj: Path) -> Path:
    """建虚拟环境并装依赖，返回可用的 python 路径。"""
    if sys.version_info < MIN_PY:
        raise SystemExit(f"✗ 需要 Python {MIN_PY[0]}.{MIN_PY[1]}+，当前是 "
                         f"{sys.version_info.major}.{sys.version_info.minor}")
    venv = proj / ".venv"
    print("· 首次运行：创建虚拟环境…")
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    py = venv / ("Scripts" if os.name == "nt" else "bin") / \
        ("python.exe" if os.name == "nt" else "python")
    print("· 安装依赖（约 1~2 分钟，仅此一次）…")
    subprocess.run([str(py), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
                   check=False)
    subprocess.run([str(py), "-m", "pip", "install", "--quiet",
                    "-r", str(proj / "requirements.txt")], check=True)
    return py


def free_port() -> None:
    if os.name == "nt":
        subprocess.run(["cmd", "/c",
                        f"for /f \"tokens=5\" %a in "
                        f"('netstat -ano ^| findstr :{PORT} ^| findstr LISTENING') "
                        f"do taskkill /F /PID %a"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return
    try:
        import signal
        out = subprocess.run(["lsof", "-nP", f"-tiTCP:{PORT}", "-sTCP:LISTEN"],
                             capture_output=True, text=True, check=False).stdout
        for pid in out.split():
            try:
                os.kill(int(pid), signal.SIGTERM)
            except (ValueError, OSError):
                pass
    except FileNotFoundError:
        pass


def wait_ready(timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            s.settimeout(0.6)
            if s.connect_ex(("127.0.0.1", PORT)) == 0:
                return True
        time.sleep(0.3)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="合同脱敏助手启动器")
    ap.add_argument("--foreground", action="store_true", help="前台运行，Ctrl-C 结束")
    args = ap.parse_args()

    proj = project_dir()
    py = pick_python(proj)
    if py is None:
        py = bootstrap(proj)

    free_port()
    workdir = proj / "sessions"
    workdir.mkdir(exist_ok=True)

    print(f"· 项目目录：{proj}")
    print(f"· Python   ：{py}")
    print(f"· 启动服务（完全离线，仅监听 127.0.0.1:{PORT}）…")

    cmd = [str(py), str(proj / "contract_app_server.py"),
           "--host", "127.0.0.1", "--port", str(PORT),
           "--workdir", str(workdir)]
    if args.foreground:
        proc = subprocess.Popen(cmd, cwd=str(proj))
    else:
        log = workdir / "server.log"
        log_f = open(log, "wb")
        proc = subprocess.Popen(cmd, cwd=str(proj),
                                stdout=log_f, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)

    if not wait_ready():
        proc.terminate()
        print(f"✗ 服务启动失败，日志：{workdir / 'server.log'}", file=sys.stderr)
        return 1

    print(f"✓ 服务已就绪：{APP_URL}")
    webbrowser.open(APP_URL)
    print("  停止服务：网页右上角「退出」，或重新运行本启动器。")

    if args.foreground:
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
