# 001-contract-desensitizer（合同脱敏 / 还原）

## 1. 一句话定位

法务、律师、行政、HR 在把合同发给外部（对方、外部顾问、投标、归档、培训示例）之前，
一键把姓名、身份证、手机号、座机、统一社会信用代码、银行账号、金额、地址等敏感信息
替换成**可逆占位符**，需要时用 mapping 还原成原文。

## 2. 快速开始

推荐从[官网](https://legaltechcc.com/workflows/contract-desensitizer/#install)下载 v1.2.1 Mac 或 Windows 包，完整解压后按外层 README 启动。工具运行不需要 AI。

请 AI Agent 帮助安装时，使用[开始使用.md](01-source/开始使用.md)中的提示。源码安装命令、系统安全提示、端口排错和测试见[完整 README](01-source/README.md)。SkillHub 上架版尚未同步本次修复。

## 3. 能力边界

| 项 | 内容 |
|---|---|
| 支持 | `.docx` / 可提取文字的 `.pdf` / `.txt` / `.md`；段落、表格、页眉页脚、文本框 |
| 支持 | 同一实体全文共用一个编号；企业全称与简称自动归并；仅 Word 内部可逆稿可还原；默认对外稿不含映射 |
| 不支持 | **扫描件（图片型 PDF）**——没有 OCR，需先做文字识别 |
| 已知限制 | 无分隔符的 800/400 号码仍可能被当作占位符跳过；浏览器不能自动写回原文件夹，需选目录授权 |
| 合规红线 | 依赖安装需要联网；合同处理离线，不调模型，只监听 `127.0.0.1`；但**不替代**本单位的合规判断流程 |
| 保密红线 | `mapping.json` 含全部原始敏感信息，**等同原件**，不能随脱敏件一起外发 |

## 4. 目录地图

| 目录 | 性质 | 内容 |
|---|---|---|
| `01-source/` | 定稿·唯一真源 | 完整工程：4 个 Python 引擎、规则清单、三平台启动器（含 macOS `.app`）、截图、回归测试、完整教程 |
| `02-github/` | 定稿·发布物料 | `CHANGELOG.md`、`RELEASE-CHECKLIST.md`（发版前自检清单） |
| `03-skillhub/` | 定稿·发布形态 | `SKILL.md` + `scripts/` + `references/`，即上传到 SkillHub 的那一份 |
| `90-build/` | 构建产物 | `build.sh`（同步+自检+打包）、`publish_to_skillhub.sh`、生成的 zip（zip 不入库） |
| `99-temp/` | 临时 | 运行会话、报告、测试样本（**不入库**） |

## 5. 维护说明

- **改代码**：只改 `01-source/`；改完跑 `bash 90-build/build.sh`（同步到 `03-skillhub/` + 自检 + 重新打包）
- **自检**：`01-source` 下 `python contract_sensitive_detector.py --selftest`、`python contract_redactor.py --selftest`
- **发 GitHub 版**：commit + push（本仓库即 GitHub 仓库）
- **发 SkillHub 版**：改 `03-skillhub/SKILL.md` 的 `version`（SemVer）→ `skillhub publish 03-skillhub --changelog "..."`
- **禁止**：手改 `03-skillhub/scripts/` 下的源码与 `references/` 下的文档，会被 `build.sh` 覆盖；
  技能包里手写的只有 `SKILL.md` 和 `scripts/launcher/start.py`

## 6. 许可与来源

MIT © 2026 whatcccup ｜ 源码：<https://github.com/whatcccup/cece_legal_skills>
｜ SkillHub：<https://skillhub.cn/skills/user_47430f88/contract-desensitizer-offline>
