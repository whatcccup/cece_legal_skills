#!/bin/bash
# ---------------------------------------------------------------------------
# contract-desensitizer 构建脚本
#
# 一个命令完成「同步 + 自检 + 打包 + 预检」：
#   1. 把 01-source/ 的源码同步到 03-skillhub/（技能包里的源码永远跟着真源走）
#   2. 跑源码自检 + 回归测试
#   3. 校验技能包里没有违规文件（.bat/.vbs/.sh、__pycache__、会话产物）
#   4. 打包 03-skillhub → 90-build/contract-desensitizer-offline.zip
#   5. 跑 skillhub --dry-run（CLI 存在时）
#
# 用法：bash 90-build/build.sh
# ---------------------------------------------------------------------------
set -u

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$SKILL_DIR/01-source"
PKG="$SKILL_DIR/03-skillhub"
OUT="$SKILL_DIR/90-build"
ZIP="$OUT/contract-desensitizer-offline.zip"

fail=0
ok()   { printf '  [OK]   %s\n' "$*"; }
bad()  { printf '  [FAIL] %s\n' "$*"; fail=1; }
info() { printf '\n== %s ==\n' "$*"; }

# ---------------------------------------------------------------- 1. 同步源码
info "1/5 同步源码 01-source → 03-skillhub"
mkdir -p "$PKG/scripts/launcher" "$PKG/references" "$PKG/tests"
for f in contract_sensitive_detector.py contract_redactor.py \
         contract_app_server.py contract_app_ui.py requirements.txt; do
  cp "$SRC/$f" "$PKG/scripts/$f" || bad "复制 $f 失败"
done
# 启动器 start.py 是技能包专属（.bat/.vbs/.sh 会被上架拦截），手写维护，不参与同步
cp "$SRC/脱敏规则清单.md" "$PKG/references/脱敏规则清单.md" || bad "复制规则清单失败"
cp "$SRC/README.md" "$PKG/references/使用说明.md" || bad "复制使用说明失败"
cp "$SRC/tests/"*.py "$SRC/tests/"*.js "$PKG/tests/" 2>/dev/null || true
ok "源码与文档已同步（SKILL.md 与 scripts/launcher/start.py 为手写，不覆盖）"

# ---------------------------------------------------------------- 2. 自检
info "2/5 源码自检"
PY="$(command -v python3 || command -v python)"
if [ -n "$PY" ]; then
  "$PY" "$PKG/scripts/contract_sensitive_detector.py" --selftest >/dev/null 2>&1 \
    && ok "识别引擎自检通过" || bad "识别引擎自检失败"
  "$PY" "$PKG/scripts/contract_redactor.py" --selftest >/dev/null 2>&1 \
    && ok "改写引擎自检通过" || bad "改写引擎自检失败"
else
  bad "未找到 python3"
fi

# ---------------------------------------------------------------- 3. 违规文件
info "3/5 上架合规扫描"
hits="$(find "$PKG" -type f \( -name '*.bat' -o -name '*.vbs' -o -name '*.sh' \
        -o -name '*.exe' -o -name '*.command' \) 2>/dev/null)"
[ -z "$hits" ] && ok "无可执行文件（.bat/.vbs/.sh 会被 SkillHub 拒绝）" \
               || bad "发现可执行文件，必须移除：$(echo "$hits" | tr '\n' ' ')"
junk="$(find "$PKG" -type d \( -name '__pycache__' -o -name '.venv' -o -name 'sessions' \) 2>/dev/null)"
[ -z "$junk" ] && ok "无缓存 / 会话产物" || bad "发现需清理目录：$(echo "$junk" | tr '\n' ' ')"
[ -f "$PKG/SKILL.md" ] && ok "SKILL.md 存在" || bad "缺少 SKILL.md"

# ---------------------------------------------------------------- 4. 打包
info "4/5 打包"
mkdir -p "$OUT"
rm -f "$ZIP"
command -v zip >/dev/null 2>&1 \
  && (cd "$(dirname "$PKG")" && zip -qr "$ZIP" "$(basename "$PKG")" -x '*.DS_Store' -x '*__pycache__*') \
  || "$PY" - "$PKG" "$ZIP" <<'PYEOF'
import os, sys, zipfile
src, out = sys.argv[1], sys.argv[2]
root = os.path.dirname(src)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for dirpath, dirnames, files in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".venv", "sessions")]
        for f in files:
            if f == ".DS_Store":
                continue
            p = os.path.join(dirpath, f)
            z.write(p, os.path.relpath(p, root))
PYEOF
[ -f "$ZIP" ] && ok "已生成 $(basename "$ZIP")（$(du -h "$ZIP" | cut -f1)）" || bad "打包失败"

# ---------------------------------------------------------------- 5. 预检
info "5/5 SkillHub 预检"
if command -v skillhub >/dev/null 2>&1 || [ -x "$HOME/.local/bin/skillhub" ]; then
  SH="skillhub"; command -v skillhub >/dev/null 2>&1 || SH="$HOME/.local/bin/skillhub"
  "$SH" publish "$PKG" --dry-run 2>&1 | tail -2
else
  echo "  [跳过] 未安装 skillhub CLI"
fi

echo
if [ "$fail" = "0" ]; then echo "== 全部通过 =="; else echo "== 存在失败项，请勿发布 =="; fi
exit "$fail"
