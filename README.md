# 合同脱敏工具

把合同中的姓名、电话、账号等敏感信息找出来，逐项确认后，再导出脱敏文件。文件在自己电脑上处理，不需要上传给 AI，也不需要模型账号或 API Key。

## 下载安装

- **Windows**：下载 Windows 安装程序，双击安装，以后从桌面“合同脱敏工具”图标打开。
- **Mac**：在“关于本机”查看芯片，选择 Apple 或 Intel 版本。下载、完整解压后，将 App 拖到“应用程序”，双击打开。

程序自带运行环境，不需要安装 Python，不影响电脑已有 Python，也不需要 AI Agent 帮忙安装。

[官网下载与说明](https://legaltechcc.com/workflows/contract-desensitizer/) · [GitHub Releases 下载](https://github.com/whatcccup/cece_legal_skills/releases)

## 怎么使用

1. 点击“选择合同”，在系统文件窗口选择一份合同副本。支持 Word、文字型 PDF、TXT 和 Markdown；扫描图片暂不支持，需要先 OCR。
2. 在左右对照中逐项复核。想保留某条信息，取消勾选即可。
3. 点击“确认并执行脱敏”，会弹出系统“另存为”窗口，默认打开原合同所在文件夹。选好位置并保存后，**脱敏文件和还原 JSON 会一起保存**，不用再下载第二次。
4. 只发送脱敏文件。发送前重新打开检查，确认没有遗漏；**不要把 JSON 发给别人或 AI**。

例如选择 `合同.docx`，会得到：

| 文件 | 用途 | 能外发吗 |
| --- | --- | --- |
| `合同_脱敏.docx` | 姓名、电话等选中内容被替换为占位符，文件内不保存原文映射 | 人工复核后，可以发给别人或 AI |
| `合同_脱敏.docx.mapping.json` | 保存占位符和敏感原文的对应关系，供自己还原 | **不可以**，含敏感原文，请单独保管 |

没有另一种“可逆 Word”，也不需要选择导出用途。两个文件会同时保存，但请勿将整个文件夹或两个文件一起发给 AI。

如需还原，在工具中切换“还原”，选择脱敏 Word。对应 JSON 在同一文件夹、文件名未改时会自动找到；否则按提示选择 JSON。丢失 JSON 就无法自动还原。PDF、TXT 与 Markdown 也会保存配套 JSON，但目前只有 Word 支持自动还原。

取消保存后不会写入所选位置，可以点击“重新保存两个文件”。已有同名文件或 JSON 时不会覆盖，请换一个新文件名。不要将脱敏文件保存为原合同的名字。

桌面 App 支持以上系统窗口。仅用源码在浏览器运行时，请手动选择保存文件夹；浏览器上传不会提供原文件的完整路径。

退出请点网页右上角“退出”，只关标签页不会停止服务。自动识别可能漏检，图片、未勾选的内容和上下文线索也需要人工检查。

## 想改规则怎么办

点击“打开规则文件”，先备份，再把文件全部内容和修改要求交给 AI Agent。请它返回完整规则，将结果复制回原文件保存，再重新上传虚构样例验证。软件里有可复制的提示词。不要发送真实合同、客户信息或原文映射。

用户规则独立保存，升级不会覆盖修改；删除 App 或卸载不会删除合同记录，请按自己的保密要求管理。

## 常见问题

- **Mac 打不开**：确认来源后先尝试打开，再到“系统设置 → 隐私与安全性”按系统提示处理。App 尚未获 Apple 公证；提示损坏或恶意软件时停止并反馈，不关闭系统防护。
- **提示端口占用**：先看是否已有工具打开；需要换版时从旧工具网页退出。程序不会结束其他软件。
- **需要安装 AI 吗**：不需要。AI Agent 只是修改规则或排错时的可选帮手。
- **在哪里看日志**：Mac 在 `~/Library/Application Support/ContractRedactor/startup.log`；Windows 在 `%LOCALAPPDATA%\ContractRedactor\Data\startup.log`。不要公开含合同信息的日志。

## 本版已知限制

v1.4.0：Apple 芯片原生、Intel/Rosetta 的启动和虚构合同导出测试已通过；Intel 物理机、旧版 macOS、Windows 实机安装和卸载仍待验证。Windows 程序尚未代码签名，Mac 仅临时签名、未公证。

## 开源与开发者

MIT 许可。源码 ZIP 统一放在 [GitHub Releases](https://github.com/whatcccup/cece_legal_skills/releases)；官网和 SkillHub 面向普通用户提供安装软件入口。开发与构建入口见 `001-contract-desensitizer/01-source/launcher/mac-bundled/README.md`、`001-contract-desensitizer/01-source/launcher/windows-installer/README.md`，回归测试在 `001-contract-desensitizer/01-source/tests/`。
