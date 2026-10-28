---
name: contract-desensitizer-offline
slug: contract-desensitizer-offline
displayName: 合同脱敏工具（离线软件）
version: "1.4.0"
summary: Windows、Mac Apple及Intel安装软件，自带运行环境；本机合同脱敏，无需安装Python或调用AI。
description: 当用户需要下载和使用离线合同脱敏工具，或修改脱敏规则时使用。按系统提供安装软件链接，不在技能包内运行合同处理脚本，不要求安装Python。支持Word、文字型PDF和文本，扫描件需先OCR。
license: MIT
homepage: https://legaltechcc.com/workflows/contract-desensitizer/
---

# 合同脱敏工具

本技能提供安装软件入口，不附带另一套Python源码。用户安装后自行在本机处理合同，不需要AI客户端、模型账号或API Key。

下载指引与软件版本均为 v1.4.0。

## 按电脑选择下载

- [Windows 安装程序](https://legaltechcc.com/assets/downloads/ContractRedactor-Setup-1.4.0.exe)：安装后从桌面图标打开。
- [Mac Apple 芯片版](https://legaltechcc.com/assets/downloads/contract-desensitizer-mac-arm64-1.4.0.zip)：完整解压，拖到“应用程序”，打开App。
- [Mac Intel 芯片版](https://legaltechcc.com/assets/downloads/contract-desensitizer-mac-x86_64-1.4.0.zip)：同上。

[官网安装、使用、QA与原理](https://legaltechcc.com/workflows/contract-desensitizer/)

## 使用说明

通过系统文件窗口选择副本，左右复核后保存，默认打开原合同所在文件夹。脱敏文件与单独 JSON 一起保存。只有一种脱敏 Word，文件不内嵌原文映射；复核后可外发或发给 AI。JSON 含敏感原文，不可外发或发给 AI，须单独保管。扫描图片暂不支持，需先OCR。程序不会结束其他软件，退出需在网页点“退出”。

修改规则时，先在软件点“打开规则文件”并备份，用户提供规则文件和具体要求后，只修改规则，返回可复制的完整Markdown，不附代码围栏或省略未修改段落。请用户保存后重新上传虚构样例验证，不要求用户上传真实合同或映射。

## 已知限制

Apple原生和Intel/Rosetta已测试；Intel物理机、旧macOS、Windows实机安装/卸载仍待验证。Mac未公证，Windows未代码签名；不自动绕过系统防护。
