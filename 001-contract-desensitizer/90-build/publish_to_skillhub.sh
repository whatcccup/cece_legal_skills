#!/bin/bash
# ---------------------------------------------------------------------------
# 把 03-skillhub 发布到 SkillHub（skillhub.cn）
#
#   0) 先跑 bash 90-build/build.sh，确保技能包是真源同步过的最新版
#   1) 打开 https://skillhub.cn → 登录（手机号+验证码）→ 个人中心 → 实名认证
#   2) 个人中心 → API keys → 创建 API key，复制一次性的 skh_xxx（关掉弹窗就看不到）
#   3) 把下面的 YOUR_TOKEN 换成它，然后：bash 90-build/publish_to_skillhub.sh
# ---------------------------------------------------------------------------
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../03-skillhub" && pwd)"
HOST="https://api.skillhub.cn"

# 如果 skillhub 命令不在 PATH 里，取消下一行注释
# export PATH="$HOME/.local/bin:$PATH"

command -v skillhub >/dev/null 2>&1 || {
  echo "未找到 skillhub CLI，正在安装…"
  curl -fsSL https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/install.sh | bash -s -- --cli-only
  export PATH="$HOME/.local/bin:$PATH"
}

# ① 登录（已完成：凭证存在 ~/.skillhub/credentials.json，本行默认注释掉）
#    换机器或 Token 失效时再取消注释，把 YOUR_TOKEN 换成新的 skh_xxx
# skillhub login --key "YOUR_TOKEN" --host "$HOST"

# ② 本地预检（不发请求，只校验 metadata + 打包）
skillhub publish "$SKILL_DIR" --host "$HOST" --dry-run

# ③ 正式发布
skillhub publish "$SKILL_DIR" --host "$HOST" --changelog "首次发布：离线合同脱敏 / 还原，实体编号一致 + 可逆还原"

echo
echo "发布请求已提交，状态为 pending_review（审核中）。"
echo "查看：https://skillhub.cn/skills/user_47430f88/contract-desensitizer-offline"
echo "      或 https://skillhub.cn → 个人中心 → 我的 Skill"
echo
echo "上架校验红线（踩过一次）：技能包里不能出现 .bat / .vbs / .sh 等可执行文件，"
echo "否则报「不允许的文件类型」。跨平台启动请用 .py。"
echo
echo "以后更新版本：改 SKILL.md 里的 version（SemVer），再跑一次第 ③ 步，"
echo "changelog 里写清楚这次改了什么。"
