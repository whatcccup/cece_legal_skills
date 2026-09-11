#!/bin/bash
# ---------------------------------------------------------------------------
# Contract Redactor · Mac 启动器（快捷方式）
#
# 真正的实现在 .app 包内：Contract_Redactor.app/Contents/Resources/launch.sh
# 本文件只是外层入口，方便在终端里直接运行：
#
#   ./launch.sh              后台常驻（与双击 .app 等价）
#   ./launch.sh --foreground 前台模式，日志留在当前终端
# ---------------------------------------------------------------------------
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$DIR/Contract_Redactor.app/Contents/Resources/launch.sh"

if [ ! -r "$SCRIPT" ]; then
    echo "✗ 找不到 $SCRIPT" >&2
    echo "  请确认 Contract_Redactor.app 与本文件在同一目录。" >&2
    exit 1
fi

chmod +x "$SCRIPT" 2>/dev/null || true
exec /bin/bash "$SCRIPT" "$@"
