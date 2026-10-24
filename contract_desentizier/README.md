# 合同脱敏 / 还原工具

**从公众号文章找到这里的朋友，工具仍然公开可用。** 此目录保留文章中的 `contract_desentizier` 拼写，作为固定入口。

- **[打开完整工具与安装教程](../001-contract-desensitizer/01-source/README.md)**
- **[查看全部源码、双击启动器与截图](../001-contract-desensitizer/01-source/)**
- **[下载完整仓库 ZIP](https://github.com/whatcccup/cece_legal_skills/archive/refs/heads/main.zip)**：下载并解压后，进入 `001-contract-desensitizer/01-source`。

## 快速开始

需要 Python 3.9+。请下载整个仓库；本目录是导航入口，可运行源码在上面的链接中。

macOS / Linux：

```bash
git clone https://github.com/whatcccup/cece_legal_skills.git
cd cece_legal_skills/001-contract-desensitizer/01-source
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python contract_app_server.py --open-browser
```

Windows（PowerShell）：

```powershell
git clone https://github.com/whatcccup/cece_legal_skills.git
cd cece_legal_skills/001-contract-desensitizer/01-source
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe contract_app_server.py --open-browser
```

浏览器访问 <http://127.0.0.1:18800/>，上传合同、复核识别结果、确认脱敏后下载。安装依赖需要联网；合同处理在本机完成。也可以按[完整教程](../001-contract-desensitizer/01-source/README.md)使用 macOS / Windows 双击启动器。

## 支持范围

支持 `.docx`、可提取文字的 `.pdf`、`.txt` / `.md`；扫描件 PDF 需要先做 OCR。自动识别结果需人工复核。需要还原时，请妥善保管映射文件；对外分享前检查交付文件，不要把映射文件一同发给接收方。

## 固定入口与维护

- 本仓库入口：[contract_desentizier](https://github.com/whatcccup/cece_legal_skills/tree/main/contract_desentizier)
- 原目录拼写入口：[contract_desensitizer](https://github.com/whatcccup/cece_legal_skills/tree/main/contract_desensitizer)
- 公众号旧仓库入口：[cece_legal_ai_skills/contract_desentizier](https://github.com/whatcccup/cece_legal_ai_skills/tree/main/contract_desentizier)

源码统一维护在 `001-contract-desensitizer/01-source`。这些兼容入口保留供已发布文章使用；今后调整源码目录时，应同步更新导航，保留入口文件。

许可：[MIT](../LICENSE)。
