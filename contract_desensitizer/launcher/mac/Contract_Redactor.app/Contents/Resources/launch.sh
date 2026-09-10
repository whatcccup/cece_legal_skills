#!/bin/bash
# ---------------------------------------------------------------------------
# Contract Redactor · macOS 启动核心
#
#   launch.sh                后台常驻模式（.app 双击用）
#   launch.sh --foreground   前台模式（Terminal 控制台用）
#
# 行为：
#   1. 释放固定端口 18800（结束上一次的服务进程）
#   2. 关掉上一次打开的 Chrome 应用窗口
#   3. 启动本地服务（完全离线，仅监听 127.0.0.1）
#   4. 就绪后用 Chrome 的「应用模式」窗口打开 http://127.0.0.1:18800/
#
# 注意：本文件是唯一实现，放在 .app 包内部（Contents/Resources/），
#       外层 launcher/mac/launch.sh 只是指向它的快捷方式。
# ---------------------------------------------------------------------------
set -u

PORT=18800
APP_URL="http://127.0.0.1:${PORT}/"
FOREGROUND=0
[ "${1:-}" = "--foreground" ] && FOREGROUND=1

# HOME 兜底（从 LaunchServices 启动时理论上一定有，但不能假设）
if [ -z "${HOME:-}" ]; then
    HOME="$(/usr/bin/dscl . -read /Users/"$(/usr/bin/id -un)" NFSHomeDirectory 2>/dev/null | /usr/bin/awk '{print $2}')"
    export HOME
fi
[ -n "${HOME:-}" ] || HOME=/tmp

LOG_DIR="$HOME/Library/Logs/ContractRedactor"
SERVER_LOG="$LOG_DIR/server.log"
LAUNCH_LOG="$LOG_DIR/launcher.log"
CHROME_PROFILE="$HOME/Library/Application Support/ContractRedactor/chrome-profile"
mkdir -p "$LOG_DIR" "$CHROME_PROFILE" 2>/dev/null || true

log() { printf '%s  %s\n' "$(date '+%H:%M:%S')" "$*" | /usr/bin/tee -a "$LAUNCH_LOG"; }

die() {
    log "✗ $*"
    /usr/bin/osascript -e "display alert \"合同脱敏 / 还原\" message \"$*\" as critical" >/dev/null 2>&1 || true
    exit 1
}

# ---------------------------------------------------------------- 定位项目根
find_proj() {
    local d="$1" i
    for i in 1 2 3 4 5 6 7 8; do
        [ -f "$d/contract_app_server.py" ] && { printf '%s' "$d"; return 0; }
        [ "$d" = "/" ] && return 1
        d="$(cd "$d/.." 2>/dev/null && pwd)" || return 1
    done
    return 1
}

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(find_proj "$SELF_DIR" || true)"
[ -z "${PROJ_DIR:-}" ] && PROJ_DIR="$(find_proj "$(pwd)" || true)"
[ -z "${PROJ_DIR:-}" ] && die "找不到 contract_app_server.py。请把本应用放在项目目录内（或与项目同级）后再试。"

# ---------------------------------------------------------------- 找 Python
has_deps() { "$1" -c "import docx, pdfplumber, pypdf, reportlab, pypdfium2, PIL" >/dev/null 2>&1; }

PY=""
for c in "$HOME/.workbuddy/binaries/python/envs/default/bin/python" \
         "$PROJ_DIR/.venv/bin/python" \
         "$(command -v python3 2>/dev/null)" \
         "$(command -v python 2>/dev/null)"; do
    [ -n "${c:-}" ] && [ -x "$c" ] && has_deps "$c" && { PY="$c"; break; }
done

if [ -z "$PY" ]; then
    BASE="$(command -v python3 || command -v python || true)"
    [ -z "$BASE" ] && die "未找到 Python 3，请先安装：brew install python"
    log "· 首次运行：创建运行环境并安装依赖（约 1~2 分钟，仅一次）…"
    VENV="$PROJ_DIR/.venv"
    "$BASE" -m venv "$VENV" >>"$LAUNCH_LOG" 2>&1 || die "创建虚拟环境失败，详见 $LAUNCH_LOG"
    "$VENV/bin/python" -m pip install --quiet --upgrade pip >>"$LAUNCH_LOG" 2>&1 || true
    "$VENV/bin/python" -m pip install --quiet python-docx pdfplumber pypdf reportlab pypdfium2 Pillow >>"$LAUNCH_LOG" 2>&1 \
        || die "依赖安装失败，详见 $LAUNCH_LOG"
    PY="$VENV/bin/python"
fi

# ---------------------------------------------------------------- 释放端口 / 清理旧实例
free_port() {
    local pids i
    pids="$(/usr/sbin/lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    [ -z "$pids" ] && return 0
    log "· 端口 $PORT 被占用，正在结束旧服务（PID: $(echo "$pids" | tr '\n' ' ')）"
    kill $pids 2>/dev/null || true
    for i in 1 2 3 4 5 6 7 8 9 10; do
        sleep 0.3
        /usr/sbin/lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || return 0
    done
    pids="$(/usr/sbin/lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
    sleep 0.4
}

free_port
/usr/bin/pkill -f "contract_app_server\.py" >/dev/null 2>&1 || true
# 只结束用本工具专用 profile 启动的 Chrome 实例，绝不误伤用户自己的 Chrome
/usr/bin/pkill -f "Google Chrome.*ContractRedactor/chrome-profile" >/dev/null 2>&1 || true
# 关掉上一次用 .command 起的 Terminal 窗口
/usr/bin/osascript >/dev/null 2>&1 <<'AS' || true
tell application "Terminal"
    repeat with w in windows
        try
            if (name of w) contains "Contract Redactor" then close w
        end try
    end repeat
end tell
AS

# ---------------------------------------------------------------- 起服务
WORKDIR="$PROJ_DIR/contract_app_sessions"
mkdir -p "$WORKDIR" 2>/dev/null || true
cd "$PROJ_DIR" 2>/dev/null || die "无法进入项目目录：$PROJ_DIR"

: >"$SERVER_LOG" 2>/dev/null || true
log "· 项目目录：$PROJ_DIR"
log "· Python  ：$PY"

if [ "$FOREGROUND" = "1" ]; then
    "$PY" "$PROJ_DIR/contract_app_server.py" --host 127.0.0.1 --port "$PORT" --workdir "$WORKDIR" &
    SERVER_PID=$!
    trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT INT TERM
else
    /usr/bin/nohup "$PY" "$PROJ_DIR/contract_app_server.py" \
        --host 127.0.0.1 --port "$PORT" --workdir "$WORKDIR" \
        >"$SERVER_LOG" 2>&1 </dev/null &
    SERVER_PID=$!
    disown $SERVER_PID 2>/dev/null || true
fi

# ---------------------------------------------------------------- 等服务就绪
ok=0
for _ in $(/usr/bin/seq 1 80); do
    if /usr/bin/curl -sf -m 1 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then ok=1; break; fi
    kill -0 "$SERVER_PID" 2>/dev/null || break
    sleep 0.25
done

if [ "$ok" != "1" ]; then
    log "✗ 服务未能启动，日志尾部："
    /usr/bin/tail -n 25 "$SERVER_LOG" 2>/dev/null | /usr/bin/tee -a "$LAUNCH_LOG" >&2 || true
    die "本地服务启动失败。日志：$SERVER_LOG"
fi

# ---------------------------------------------------------------- 用 Chrome 应用窗口打开
open_ui() {
    if [ -d "/Applications/Google Chrome.app" ]; then
        log "· 用 Chrome 应用窗口打开 $APP_URL"
        /usr/bin/open -na "Google Chrome" --args \
            --app="$APP_URL" \
            --user-data-dir="$CHROME_PROFILE" \
            --no-first-run --no-default-browser-check
        return 0
    fi
    log "· 未检测到 Chrome，改用默认浏览器打开"
    /usr/bin/open "$APP_URL"
}

sleep 0.4
open_ui

if [ "$FOREGROUND" = "1" ]; then
    log "✓ 服务运行中：$APP_URL   （按 Ctrl-C 结束）"
    wait "$SERVER_PID"
else
    log "✓ 已在 Chrome 中打开应用窗口；关闭窗口后服务仍在后台运行，"
    log "  需要停止时点网页右上角「退出」，或再次双击本应用。"
fi
exit 0
