# 发版前自检清单（contract-desensitizer）

发布到 **GitHub** 与 **SkillHub** 前，逐条打勾。任何一条不过，不许发。

## A. 源码（01-source）

- [ ] `python contract_sensitive_detector.py --selftest` 通过
- [ ] `python contract_redactor.py --selftest` 通过
- [ ] `tests/` 下回归测试全部通过
- [ ] 拿一份真实合同跑通：上传 → 勾选 → 脱敏 → 还原，还原稿与原稿逐字一致
- [ ] `脱敏规则清单.md` 与代码里的规则同步更新（规则清单是唯一事实源）
- [ ] `docs/images/` 截图与当前界面一致（界面改过就必须重截）

## B. 构建（90-build）

- [ ] 跑过 `bash 90-build/build.sh`，输出「全部通过」
- [ ] `03-skillhub/scripts/` 下的源码与 `01-source/` 完全一致（build.sh 已同步）
- [ ] 技能包内**没有** `.bat` / `.vbs` / `.sh` 等可执行文件（会被上架校验拦截）
- [ ] 技能包内**没有** `__pycache__` / `.venv` / `sessions` / 真实合同样本
- [ ] 重新生成了 `90-build/contract-desensitizer-offline.zip`

## C. GitHub

- [ ] `git status` 干净，无临时文件（会话、mapping、脱敏稿都应躺在 `99-temp/`）
- [ ] 根 `README.md` 的技能索引表已更新（编号、名称、一句话定位、状态）
- [ ] `02-github/CHANGELOG.md` 已补本次变更（日期 / 版本 / 变更 / 影响面）
- [ ] `001-contract-desensitizer/README.md` 六段齐全，链接有效

## D. SkillHub

- [ ] `03-skillhub/SKILL.md` 的 `version` 已按 SemVer 递增（1.0.1 → 1.0.2，不能写 `1.1`）
- [ ] frontmatter 五件套齐全：`slug` / `version` / `displayName` / `description_zh` / `description_en`
- [ ] `skillhub publish 03-skillhub --dry-run` 通过
- [ ] 正式发布后核对返回：`ok=true`、版本号、`reviewStatus`
- [ ] 同步刷新三处：GitHub commit、本机 `~/.workbuddy/skills/<slug>/`、`90-build/*.zip`

## E. 发布后

- [ ] 详情页打开正常：<https://skillhub.cn/skills/user_47430f88/contract-desensitizer-offline>
- [ ] 安装命令在新环境下验证一次（含 `--dir`）
- [ ] 把结果记进 `.workbuddy/memory/` 当日日志
