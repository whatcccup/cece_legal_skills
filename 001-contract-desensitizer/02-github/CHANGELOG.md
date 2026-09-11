# 变更记录（contract-desensitizer）

格式：日期 ｜ 版本 ｜ 变更 ｜ 影响面（源码 / 技能包 / 文档）

## 2026-09-11 ｜ 仓库结构 v2 ｜ 重构 ｜ 文档

- 技能文件夹改为三位数字编号 `001-contract-desensitizer/`
- 目录拆分为 `01-source` / `02-github` / `03-skillhub` / `90-build` / `99-temp`
- 新增仓库级《目录规范》《README 规范》与技能卡片模板 `templates/skill-README.md`
- 新增 `90-build/build.sh`：一键同步源码到技能包 + 自检 + 打包
- 旧路径 `contract_desensitizer/`、`skills/` 已迁入新结构（Git 历史保留为 rename）

## 2026-09-10 ｜ 技能 1.0.1 ｜ 文档 ｜ 技能包

- `SKILL.md` 补安装命令与 `--dir` 说明（不写 `--dir` 会装到 `./skills/`，客户端识别不到）
- 使用章节标注技能版启动入口为 `scripts/launcher/start.py`

## 2026-09-10 ｜ 技能 1.0.0 ｜ 首发 ｜ 技能包

- 上架 SkillHub：`contract-desensitizer-offline`
- 上架校验拦截 `.bat` / `.vbs` / `.sh`，跨平台启动改为纯 Python `start.py`
- 技能包内含：4 个引擎 + 规则清单 + 完整教程 + 回归测试（14 个文件，128KB）

## 2026-09-10 ｜ 应用 v1.1.0 ｜ 修复 ｜ 源码

- **实体编号一致性**（核心）：同一个实体全文共用一个编号，企业全称与简称自动归并
- 修复座机 `010-xxxx xxxx`、统一社会信用代码漏检
- 修复还原保真：按出现位置逐处还原，结果与原文件逐字一致
- 修复「确认并修复」时未保存 mapping、未按勾选位置生效的问题
- 保存区默认同时下载 docx + mapping.json，支持选文件夹直写

## 2026-09-10 ｜ 仓库 v1 ｜ 首发 ｜ 仓库

- GitHub 公开仓库 `cece_legal_skills`，MIT 许可
