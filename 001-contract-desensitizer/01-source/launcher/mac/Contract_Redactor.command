#!/bin/bash
# ---------------------------------------------------------------------------
# Contract Redactor · Mac 启动器（双击即可）
#   Terminal 窗口会保留为服务控制台，按 Ctrl-C 结束服务。
#   想要「无终端窗口」的体验，请双击同目录下的 Contract_Redactor.app
# ---------------------------------------------------------------------------
printf '\033]0;Contract Redactor\007'
clear
cat <<'BANNER'
  ┌──────────────────────────────────────────────────────────┐
  │   合同脱敏 / 还原  ·  Contract Redactor                    │
  │   完全离线运行 · 所有处理都在本机完成                        │
  └──────────────────────────────────────────────────────────┘
BANNER
echo
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /bin/bash "$DIR/launch.sh" --foreground
