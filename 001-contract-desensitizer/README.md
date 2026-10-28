# 合同脱敏工具

把合同中的姓名、电话、账号等敏感信息找出来，逐项确认后，再导出脱敏文件。文件在自己电脑上处理，不需要上传给 AI，也不需要模型账号或 API Key。

## 下载安装

- **Windows**：下载 Windows 安装程序，双击安装，以后从桌面“合同脱敏工具”图标打开。
- **Mac**：在“关于本机”查看芯片，选择 Apple 或 Intel 版本。下载、完整解压后，将 App 拖到“应用程序”，双击打开。

程序自带运行环境，不需要安装 Python，不影响电脑已有 Python，也不需要 AI Agent 帮忙安装。

[官网下载与说明](https://legaltechcc.com/workflows/contract-desensitizer/) · [GitHub Releases 下载](https://github.com/whatcccup/cece_legal_skills/releases)

## 怎么使用

1. 上传一份合同副本。支持 Word、文字型 PDF、TXT 和 Markdown；扫描图片暂不支持，需要先 OCR。
2. 在左右对照中逐项复核。想保留某条信息，取消勾选即可。
3. 发给别人，选择默认“对外脱敏稿”；仅供内部还原时，选择 Word“内部可逆稿”。
4. 导出后再检查一遍，确认无遗漏。退出请点网页右上角“退出”，只关标签页不会停止服务。

**内部可逆稿仍含原文映射，不要当成对外稿发送。**自动识别可能漏检，不能代替人工通读。

## 想改规则怎么办

点击“打开规则文件”，先备份，再把文件全部内容和修改要求交给 AI Agent。请它返回完整规则，将结果复制回原文件保存，再重新上传虚构样例验证。软件里有可复制的提示词。不要发送真实合同、客户信息或原文映射。

用户规则独立保存，升级不会覆盖修改；删除 App 或卸载不会删除合同记录，请按自己的保密要求管理。

## 常见问题

- **Mac 打不开**：确认来源后先尝试打开，再到“系统设置 → 隐私与安全性”按系统提示处理。App 尚未获 Apple 公证；提示损坏或恶意软件时停止并反馈，不关闭系统防护。
- **提示端口占用**：先看是否已有工具打开；需要换版时从旧工具网页退出。程序不会结束其他软件。
- **需要安装 AI 吗**：不需要。AI Agent 只是修改规则或排错时的可选帮手。
- **在哪里看日志**：Mac 在 `~/Library/Application Support/ContractRedactor/startup.log`；Windows 在 `%LOCALAPPDATA%\ContractRedactor\Data\startup.log`。不要公开含合同信息的日志。

## 本版已知限制

v1.3.0：Apple 芯片原生、Intel/Rosetta 的启动和虚构合同导出测试已通过；Intel 物理机、旧版 macOS、Windows 实机安装和卸载仍待验证。Windows 程序尚未代码签名，Mac 仅临时签名、未公证。

## 开源与开发者

MIT 许可。源码 ZIP 统一放在 [GitHub Releases](https://github.com/whatcccup/cece_legal_skills/releases)；官网和 SkillHub 面向普通用户提供安装软件入口。开发与构建入口见 `001-contract-desensitizer/01-source/launcher/mac-bundled/README.md`、`001-contract-desensitizer/01-source/launcher/windows-installer/README.md`，回归测试在 `tests/`。
