---
name: contract-desensitizer-offline
slug: contract-desensitizer-offline
displayName: 合同脱敏助手（本机离线）
version: "1.2.1"
summary: 本机离线合同脱敏，默认对外稿不附原文映射；Word 内部可逆稿可还原。无需模型或 API Key。
description: 当用户需要识别合同敏感信息、复核并导出脱敏稿，或还原 Word 内部可逆稿时使用。支持 docx、文字型 pdf、txt、md；扫描件需先 OCR。
license: MIT
homepage: https://legaltechcc.com/workflows/contract-desensitizer/
category: professional
tags:
  - 法律
  - 合同
  - 脱敏
  - offline
---

# 合同脱敏助手 v1.2.1

核心代码、规则与官网安装包、GitHub `001-contract-desensitizer/01-source` 的 v1.2.1 一致。此技能包采用 Python 启动器，官网另有 Mac App 和 Windows 启动文件。

## 安装与启动

需要 Python 3.9+。首次联网安装依赖，合同处理在本机离线运行，不调用模型，不需要 AI 客户端或 API Key。实际测试 macOS / Python 3.12；Windows 未实机验证。

进入本技能的 `scripts` 目录执行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python launcher/start.py --foreground
```

Windows PowerShell 使用 `py -3 -m venv .venv`，后续 Python 路径为 `.venv\Scripts\python.exe`。也可直接运行 `contract_app_server.py --open-browser`。

访问 `http://127.0.0.1:18800/`。端口占用时使用已打开的工具，或在原窗口退出服务；启动器不会结束其他进程。手动运行服务器可指定 `--port 18810`。

## 操作流程

1. 使用合同副本，上传后让用户逐项复核识别结果，确认需要脱敏的位置。
2. 对外发送默认选择“对外脱敏稿”：不附还原映射，不生成明文审计日志。Word 清理自定义 XML 和文档元数据，遇未支持内容时停止导出。
3. 仅当用户需要内部还原时，选择 Word“内部可逆稿”；它内嵌含原文的映射，应按原合同等级保管，不能直接对外发送。PDF 和文本不提供自动还原。
4. 导出后检查正文、表格、页眉页脚等位置；图片文字、复杂域和未提取内容需额外检查。不得以自动检测结果代替人工复核。
5. `scripts/contract_app_sessions` 或启动器的 `scripts/sessions` 可能保留原文、结果与映射；退出不会删除文件，按用户留存要求处理。

命令行从 `scripts` 目录运行，先查看 `--help`。默认 `--export-mode external`，内部 Word 使用 `--export-mode reversible`；还原使用 `--restore`。不擅自扩大用户选择范围，不覆盖原件。

## 参考与验证

- `references/使用说明.md`：源代码版安装、功能、限制与测试命令；技能版源码位于 `scripts`，与仓库源码路径不同。
- `references/开始使用.md`：官网 ZIP 的普通用户安装说明，包含系统安全提示与排错。
- `scripts/脱敏规则清单.md`：运行时读取的规则；`references` 中保留同一份文档供查阅。
- `SOURCE-MANIFEST.json`：对应 GitHub 源码提交与逐文件 SHA-256。

核心自检：在 `scripts` 目录运行 `python contract_sensitive_detector.py --selftest`、`python contract_redactor.py --selftest`。完整平台启动器测试针对 GitHub / 官网完整工程；技能包不含 `.app`、`.bat`、`.vbs` 或 `.sh`。

MIT；源码：https://github.com/whatcccup/cece_legal_skills
