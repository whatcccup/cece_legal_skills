# 源码启动器（供开发、排错使用）

普通用户请从 https://legaltechcc.com/workflows/contract-desensitizer/#install 下载 Windows 安装程序，安装后从桌面图标启动。程序自带 Python 和依赖，不需要运行本目录的 VBS 或 BAT，也不需要另装 Python。

本目录为源码运行入口，需要 Python 3.9 或以上版本；首次安装依赖需要联网。

- Windows：完整解压源码，双击 `windows/Contract_Redactor.vbs`；排错运行同目录 `Contract_Redactor.bat`，保留窗口中的错误信息。VBS 会显示启动窗口。
- Windows BAT 必须保留 CRLF 行尾和 UTF-8 编码，不添加 BOM；编辑器保存时不要改为 LF。仓库属性与测试会检查这一要求。
- Mac：旧源码入口为 `mac/Contract_Redactor.app`，或运行 `mac/Contract_Redactor.command` 查看终端输出；普通用户使用官网自带运行环境的 App。
- 默认地址为 `http://127.0.0.1:18800/`，仅本机可访问。端口占用时会提示，不会强制结束其他程序；已运行的工具可通过网页“退出”停止。

源码环境已准备好时，也可在工具根目录运行：

```bat
.venv\Scripts\python.exe contract_app_server.py --host 127.0.0.1 --port 18800 --workdir contract_app_sessions --open-browser
```

源码启动器的格式检查不能代替 Windows 实机双击验收。使用及文件保密说明见上一级 README。
