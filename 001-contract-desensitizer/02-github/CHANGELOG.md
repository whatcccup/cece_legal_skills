# v1.3.0 · 2026-10-28

Mac Apple/Intel App、Windows安装程序自带运行环境；规则独立保存并可从软件打开，提供AI Agent修改提示词；官网改为安装、使用、QA、原理四部分，源码ZIP仅在GitHub Release提供。

已知限制：Windows实机安装/卸载、Intel物理机及旧macOS仍待验证；未做Developer ID公证或Windows代码签名。

# 变更记录（contract-desensitizer）

格式：日期 ｜ 版本 ｜ 变更 ｜ 影响面（源码 / 技能包 / 文档）

## 2026-10-28 ｜ 应用 v1.2.1 ｜ 源码、测试、说明

- 同步官网安装包采用的修复源码、Mac / Windows 启动器与说明。
- 对外稿默认不附原文映射，内部可逆稿单独命名；改写前校验文字位置，补充 Word 元数据及不支持内容检查。
- 对比位置显示“第 N 段”，点击命中项与段落同步定位左右两栏。
- 加固本机接口访问、请求大小与并发限制；端口占用不结束其他进程，补充实际启动错误提示。
- 补充回归与服务、启动器测试，下载测试使用虚构样例。
- 官网 ZIP 外层直接提供 App 或 Start 启动文件、README 和 AI 安装提示，其余源码与测试收纳至“其他资料”。
- Windows 尚未实机验证；SkillHub 本次未上架更新。

## 2026-10-24 ｜ 兼容入口恢复 ｜ 文档

- 恢复 `contract_desensitizer/` 原目录导航入口，补充公众号使用的 `contract_desentizier/` 拼写入口。
- 保留 `cece_legal_ai_skills` 旧仓库名称作为公开导航入口，统一指向本仓库源码。
- 仓库首页增加公众号读者入口，附完整下载链接与 macOS / Linux / Windows 安装命令。
- 兼容入口应长期保留；源码目录如有调整，更新导航链接，不删除入口。

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
