---
name: contract-desensitizer-offline
slug: contract-desensitizer-offline
displayName: 合同脱敏助手（离线可逆）
display_name: 合同脱敏助手（离线可逆）
display_name_en: Contract Desensitizer (Offline Reversible)
version: "1.0.1"
summary: >-
  本地离线合同脱敏与还原工具：识别姓名、身份证、手机号、座机、统一社会信用代码、银行账号、金额、地址等敏感信息，
  替换为「同一实体全文共用一个编号」的可逆占位符，支持一键还原成原文，docx/pdf/txt 全格式，不联网、不调大模型。
description_zh: >-
  本地离线运行的合同脱敏与还原工具。当用户需要把合同、协议、招投标文件等法务文档发给外部（对方、外部律师、
  顾问、投标、归档、培训示例）但必须先去掉敏感信息时使用。识别姓名、身份证、手机号、座机、统一社会信用代码、
  银行账号、金额、地址、邮箱等，替换成同一实体全文共用一个编号的可逆占位符（如「甲方 [姓名#1]」），
  并生成 mapping.json 支持一键还原成原文。支持 docx / pdf / txt / md，保留表格、页眉页脚与原有格式，
  完全离线、不调云端大模型。触发词包括：合同脱敏、合同去隐私、协议脱敏、合同打码、敏感信息替换、
  合同还原、脱敏后恢复原文、文档脱敏、法务脱敏。
description_en: >-
  Offline contract desensitization and restoration toolkit. Use when a contract, agreement or legal document must be
  shared externally (counterparty, outside counsel, bidding, archiving) but sensitive data must be removed first.
  Detects names, ID card numbers, mobile and landline phones, unified social credit codes, bank accounts, amounts and
  addresses, then replaces them with reversible placeholders where one entity keeps one number across the whole
  document. A mapping.json enables pixel-faithful one-click restoration. Works on docx, pdf, txt and md, keeps tables,
  headers and formatting intact, and never calls a cloud LLM.
description: >-
  本地离线合同脱敏与还原：识别并替换敏感信息为全文编号一致的可逆占位符，生成 mapping.json 支持一键还原，
  支持 docx/pdf/txt/md，完全离线。触发词：合同脱敏、合同去隐私、协议脱敏、合同还原、文档脱敏。
license: MIT
homepage: https://github.com/whatcccup/cece_legal_skills
category: professional
tags:
  - 法律
  - 合同
  - 脱敏
  - 隐私
  - offline
  - docx
  - redaction
---

# 合同脱敏助手（离线 · 可逆 · 实体编号一致）

把合同里的敏感信息**一键替换成可逆占位符**，需要时再**一键还原**成原文。
面向法务、律师、行政、HR 等需要把合同发给外部的场景。

> 安装：`skillhub install contract-desensitizer-offline --namespace user_47430f88 --dir <你的 skills 目录>`
> （WorkBuddy `~/.workbuddy/skills`、Claude Code `~/.claude/skills`、Cursor `~/.cursor/skills`、Codex `~/.codex/skills`；
> 默认会装到 `./skills/`，客户端识别不到，所以 `--dir` 不能省。）

## 为什么用它，而不是让大模型直接改

| 维度 | 本技能 | 让大模型通读改写 |
|---|---|---|
| 同一实体编号 | 全文统一：`张三` 永远是 `[姓名#1]`，简称「星海智能」与全称「星海智能科技有限公司」自动合并为同一编号 | 容易前后编号打架，长合同几乎必错 |
| 可逆 | `mapping.json` 一对一映射，还原后与原文件逐字一致 | 不可逆，原文丢失 |
| 结构 | 只改文字，批注 / 修订 / 样式 / 字体 / 表格全部保留 | 常被重排版 |
| 合规 | 100% 离线，不调云端大模型，不分片上传，只监听 `127.0.0.1` | 合同正文要出境到模型服务商 |
| 可审计 | 每次输出审计日志 + 规则命中报告 | 无 |

**红线**：涉及国家秘密、个人敏感信息批量处理时，仍应先走本单位合规流程；本技能只做技术处理，不替代合规判断。

---

## 何时触发

用户说以下任意一种，就应使用本技能：

- 「帮我把这份合同脱敏 / 去隐私 / 打码 / 去掉敏感信息」
- 「这份合同要发给外部律师 / 对方 / 投标，先处理一下」
- 「脱敏后的合同怎么还原回原文」
- 「合同里有哪些个人信息 / 敏感信息，列个清单」
- 附带 `.docx` / `.pdf` 并提到「敏感」「保密」「不能外传」「脱敏」

---

## 环境准备（首次使用时做一次）

```bash
SKILL_DIR="<本技能所在目录>"        # 例如 ~/.workbuddy/skills/contract-desensitizer
cd "$SKILL_DIR/scripts"

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt      # Windows 用 .venv\Scripts\python

# 自检（两条都应输出通过）
.venv/bin/python contract_sensitive_detector.py --selftest
.venv/bin/python contract_redactor.py --selftest
```

依赖全部是本地解析 / 渲染库（python-docx、pdfplumber、pypdf、reportlab、pypdfium2、Pillow），运行时不联网。
需要 Python 3.9+（已在 3.13 上完整验证）。

**Web 界面**（推荐给非技术用户）：

```bash
python "$SKILL_DIR/scripts/launcher/start.py"        # Windows / macOS / Linux 通用，自动开浏览器
# 或手动：.venv/bin/python contract_app_server.py --host 127.0.0.1 --port 18800
```

启动后访问 `http://127.0.0.1:18800/`，上传 → 左右对比勾选 → 确认 → 下载 `_脱敏.docx` + `mapping.json`。

---

## 标准工作流

### 1. 先识别，出报告（不要直接改）

```bash
.venv/bin/python contract_sensitive_detector.py 合同.docx \
    --out-dir ./reports --format json,csv,txt,html
```

产出：敏感信息清单（json / csv / txt）+ 一个自包含的复查页 html。
先把清单给用户看一眼，确认哪些要脱敏、哪些要保留（比如甲方自己的名称通常要保留）。

常用参数：
- `--only TYPE1,TYPE2` 只启用指定类型
- `--disable TYPE` 停用指定类型
- `--enable TYPE` 强制启用默认关闭的类型（如 `IPV4`、`MAC_ADDRESS`）
- `--allowlist allowlist.txt` 白名单文件，每行一个值，命中即忽略
- `--min-confidence 0.6` / `--min-severity high` 阈值过滤

### 2. 脱敏

命令行（按类型）：

```bash
.venv/bin/python contract_redactor.py 合同.docx \
    --types PERSON_NAME,PHONE_MOBILE,ID_CARD,USCC,BANK_ACCOUNT \
    --restore-mode
```

按复查页导出结果脱敏（尊重用户逐个勾选的位置，推荐）：

```bash
.venv/bin/python contract_redactor.py 合同.docx \
    --selection 合同.selection.json --restore-mode
```

产出：`<原名>_脱敏.docx` + `<原名>.mapping.json`（占位符 ↔ 原文，可还原）。

**务必提醒用户**：`mapping.json` 本身含全部原始敏感信息，等同于原件，必须按原件密级保管，不能随脱敏件一起外发。

### 3. 还原

```bash
.venv/bin/python contract_redactor.py 合同_脱敏.docx --restore
```

还原只改写文字内容，批注 / 修订 / 样式 / 字体完全保留，结果与原文件逐字一致。

### 4. 收尾自查

- 打开脱敏件搜索残留的公司名、人名、电话、账号
- 确认表格、页眉页脚、文本框中的内容也被处理（工具已覆盖，仍需抽查）
- 确认 `mapping.json` 已归档到受控位置

---

## 能识别什么

完整规则表见 `references/脱敏规则清单.md`，核心类型：

| 类别 | 类型 |
|---|---|
| 主体 | 人名、企业名称（含简称合并）、统一社会信用代码、身份证、护照、港澳台通行证 |
| 联系 | 手机号、座机（含 010-xxxx xxxx、400/800）、邮箱、通信地址 |
| 资金 | 银行账号、银行卡号、金额（大小写人民币）、税号 |
| 其他 | 日期、IP / MAC、车牌、URL、统一社会信用代码、组织机构代码 |
| 关闭项 | IPV4、MAC_ADDRESS 等默认关闭，用 `--enable` 打开 |

两个不能踩的已知边界：

1. **扫描件（图片型 PDF）识别不了** —— 没有 OCR，需要先做文字识别。
2. **占位符本身不会被二次脱敏** —— 工具会跳过 `[姓名#1]` 这类已有占位符，避免重复替换。

---

## 如何修改

| 想改什么 | 改哪里 |
|---|---|
| 增删识别类型、调正则、调置信度 | `scripts/contract_sensitive_detector.py` 的 `RULES` / `TYPE_META`；规则文档同步更新 `references/脱敏规则清单.md` |
| 占位符格式（`[姓名#1]`） | `EntityNumberer.placeholder()` |
| 企业简称合并策略 | `org_core_variants()` / `_org_same_entity()` |
| 脱敏后文本掩码样式（`138****5678`） | `scripts/contract_redactor.py` 的掩码函数 |
| 界面文案 / 视觉 | `scripts/contract_app_ui.py`（纯模板层，与服务端解耦） |
| 服务端行为 / 接口 | `scripts/contract_app_server.py` |

改完必须跑：

```bash
.venv/bin/python contract_sensitive_detector.py --selftest
.venv/bin/python contract_redactor.py --selftest
.venv/bin/python tests/test_entity_consistency.py
.venv/bin/python tests/test_app_e2e.py
.venv/bin/python tests/test_output_download.py
```

全部通过再提交。`tests/` 里的样例均为合成文本，不含真实合同。

---

## 目录结构

```
contract-desensitizer/
├── SKILL.md                      本文件
├── scripts/
│   ├── contract_sensitive_detector.py   识别引擎（含 --selftest）
│   ├── contract_redactor.py             脱敏 / 还原引擎（含 --selftest）
│   ├── contract_app_server.py           本地 Web 服务（127.0.0.1:18800）
│   ├── contract_app_ui.py               Web 界面模板层
│   ├── requirements.txt
│   └── launcher/                        start.py（跨平台启动器）+ 说明
├── references/
│   ├── 脱敏规则清单.md                   规则单一事实源
│   └── 使用说明.md                       完整安装与使用教程
└── tests/                               回归测试（合成数据）
```

---

## 常见问题

**Q：能不能做成双击图标？**
GitHub 仓库里的完整版带 macOS `.app` 与 Windows `.vbs` 图标；技能包只保留跨平台的
`start.py`（上架平台会拦截 `.bat` / `.vbs` / `.sh` 这类可执行文件）。
想在本地做快捷方式：macOS 把 `python <绝对路径>/start.py` 存成 `.command`，
Windows 存成 `.bat`，首次运行若被系统拦截，右键 → 打开 → 确认即可。

**Q：端口 18800 被占用？**
启动器会自动结束旧服务；也可以手动 `lsof -nP -tiTCP:18800 | xargs kill`。

**Q：浏览器不能自动把文件存回原文件夹？**
浏览器安全限制所致。界面默认勾选"同时下载 docx + mapping.json"，也可点"选择文件夹"授权后直写到该目录（Chrome / Edge 支持）。

**Q：脱敏后能否再编辑正文结构（删段落、改表格）？**
可以，但还原依赖占位符与原文一一对应；删掉含占位符的段落会让该处无法还原，其余不受影响。

**Q：会联网吗？**
不会。默认 `enforce_offline()` 主动阻断外联；只有绑定端口的服务模式才开闸，且只绑 `127.0.0.1`。确有需要时用 `--allow-network` 显式放开。

---

## 许可与来源

MIT。源码与更新：<https://github.com/whatcccup/cece_legal_skills>
