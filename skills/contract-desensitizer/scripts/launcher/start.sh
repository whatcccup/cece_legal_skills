#!/bin/bash
# ---------------------------------------------------------------------------
# 合同脱敏助手 · macOS / Linux 启动器
#
#   ./start.sh                启动本地服务并自动打开浏览器（推荐，双击即可）
#   ./start.sh --foreground   前台运行，日志留在当前终端，Ctrl-C 结束
#
# 行为：
#   1. 找到带依赖的 Python；没有就自动建 .venv 并安装 requirements.txt（仅首次）
#   2. 释放 18800 端口、结束上一次的服务进程
#   3. 启动本地服务（完全离线，仅监听 127.0.0.1）
#   4. 就绪后打开 http://127.0.0.1:18800/
# ---------------------------------------------------------------------------
set -u

PORT=18800
APP_URL="http://127.0.0.1:${PORT}/"
FOREGROUND=0
[ "${1:-}" = "--foreground" ] && FOREGROUND=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------- 找 Python
has_deps() {
  "$1" -c "import docx, pdfplumber, pypdf, reportlab, pypdfium2, PIL" >/dev/null 2>&1
}

PY=""
for c in "$PROJ_DIR/.venv/bin/python" \
         "$(command -v python3 2>/dev/null)" \
         "$(command -v python 2>/dev/null)"; do
  [ -n "${c:-}" ] && [ -x "$c" ] && has_deps "$c" && { PY="$c"; break; }
done

if [ -z "$PY" ]; then
  BASE="$(command -v python3 || command -v python || true)"
  if [ -z "$BASE" ]; then
    echo "✗ 未找到 Python 3，请先安装（macOS: brew install python）" >&2
    exit 1
  fi
  echo "· 首次运行：创建虚拟环境并安装依赖（约 1~2 分钟，仅此一次）…"
  VENV="$PROJ_DIR/.venv"
  "$BASE" -m venv "$VENV" || { echo "✗ 创建虚拟环境失败" >&2; exit 1; }
  "$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
  "$VENV/bin/python" -m pip install --quiet -r "$PROJ_DIR/requirements.txt" \
    || { echo "✗ 依赖安装失败，请检查网络后重试" >&2; exit 1; }
  PY="$VENV/bin/python"
fi

# ---------------------------------------------------------------- 释放端口
pids="$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
[ -n "$pids" ] && kill $pids 2>/dev/null || true
pkill -f "contract_app_server\.py" >/dev/null 2>&1 || true
sleep 0.5

# ---------------------------------------------------------------- 起服务
WORKDIR="$PROJ_DIR/sessions"
mkdir -p "$WORKDIR" 2>/dev/null || true
cd "$PROJ_DIR" || { echo "✗ 无法进入 $PROJ_DIR" >&2; exit 1; }

echo "· 项目目录：$PROJ_DIR"
echo "· Python   ：$PY"

if [ "$FOREGROUND" = "1" ]; then
  "$PY" "$PROJ_DIR/contract_app_server.py" --host 127.0.0.1 --port "$PORT" --workdir "$WORKDIR" &
  SERVER_PID=$!
  trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT INT TERM
else
  nohup "$PY" "$PROJ_DIR/contract_app_server.py" \
      --host 127.0.0.1 --port "$PORT" --workdir "$WORKDIR" \
      >"$WORKDIR/server.log" 2>&1 </dev/null &
  SERVER_PID=$!
  disown $SERVER_PID 2>/dev/null || true
fi

ok=0
for _ in $(seq 1 80); do
  if curl -sf -m 1 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then ok=1; break; fi
  kill -0 "$SERVER_PID" 2>/dev/null || break
  sleep 0.25
done

if [ "$ok" != "1" ]; then
  echo "✗ 服务启动失败，日志：$WORKDIR/server.log" >&2
  tail -n 25 "$WORKDIR/server.log" 2>/dev/null >&2 || true
  exit 1
fi

echo "✓ 服务已就绪：$APP_URL"
if command -v open >/dev/null 2>&1; then
  open "$APP_URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$APP_URL"
fi
echo "  停止服务：网页右上角「退出」，或重新运行本启动器。"

if [ "$FOREGROUND" = "1" ]; then
  wait "$SERVER_PID"
fi
exit 0
