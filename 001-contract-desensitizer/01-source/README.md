# 合同脱敏 / 还原工具 v1.2.1

提供 Mac 和 Windows ZIP 包，含 Python 源码、对应启动器、规则、说明与测试。需要 Python 3.9+；本轮实际测试为 macOS / Python 3.12。Windows 启动脚本已静态检查，尚未完成 Windows 实机验证。

安装依赖时需要联网。准备好环境后，合同识别、脱敏与还原在本机进行，**无需 AI 客户端、模型账号或 API Key**。Python 处理进程限制外部 TCP、DNS 和 UDP，请求本机服务仍正常；这不是操作系统级安全沙箱或完整安全审计。

## 安装与启动

先完整解压 ZIP，不要在压缩包内直接启动。Mac 可将 App 放到方便的位置。

**Windows：请先解压整个 ZIP，再双击文件夹里的 `Start.vbs` 启动。不要单独移动或删除 `Start.vbs`、`Start.bat` 和 `_support` 文件夹；需要换位置时，把整个文件夹一起移动。**

从 GitHub 下载完整仓库后，先进入 `001-contract-desensitizer/01-source`；以下命令均在该目录执行。官网 ZIP 使用外层《README-先读.md》的双击启动步骤；若手动运行，Mac 源码在 App 的 `Contents/Resources/tool`，Windows 源码在 `_support`。

首次准备环境：

macOS：
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python contract_app_server.py --open-browser
```
Windows PowerShell：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe contract_app_server.py --open-browser
```

后续可双击 `launcher/mac/Contract_Redactor.app` 或 `launcher/windows/Contract_Redactor.vbs`，浏览器访问 `http://127.0.0.1:18800/`。Mac排错可用 `.command`，Windows排错可用 `.bat`。

启动器会在缺少依赖时尝试首次安装；联网准备只发生在此阶段。系统安全拦截时按系统提示核查来源，不要盲目关闭系统防护。端口已被占用时停止并提示，**不会结束无关进程**。需要另一个端口，可命令行指定 `--port 18810`。旧服务请通过原窗口的“退出”自行关闭。

## 使用与导出模式

1. 上传合同副本，左右对照全部提取文字。
2. 逐项确认类型和位置，取消不需要的替换。
3. 选择导出用途，确认执行后保存。

- **对外脱敏稿（默认）**：使用占位符，不生成还原映射和明文日志；Word清理自定义XML、还原映射和文档元数据。遇嵌入附件、活动控件等未支持内容时停止导出，需先移除。它不是不可逆匿名化或数据合规保证，发送前仍应人工复核。
- **内部可逆稿**：Word内嵌含原文的 `customXml/mapping.json`，另可保存JSON对照表。上传内部稿即可还原。该稿件及映射应按原合同相应等级保管，不应直接发送给不受信任的接收方。

Word识别与改写共用同一文字位置映射，覆盖正文、表格、文本框、普通/首页/偶数页页眉页脚、批注、脚注/尾注和修订中的可提取文字。替换前核对原文，不一致则停止。原件不会被覆盖。

支持 `.docx`、文字型 `.pdf`、`.txt` / `.md`。PDF只将命中页栅格化并遮罩，未命中页保留原页；PDF不能自动还原。文本文件也不提供自动还原。图片中的文字、手写、图表、公式、复杂域代码和其他未提取内容需要另行检查；扫描件需先OCR。

## 自定义规则

编辑《脱敏规则清单.md》。网页与改写器共用加载入口，新增正则规则会在每次加载时重新编译。改完后重新上传复核，勿沿用旧位置选择。出现无效规则会报错，不会静默忽略。

## 本地数据

`contract_app_sessions/` 含上传原文、报告、映射及结果；退出服务不等于删除这些文件。请将该目录保存在受控位置，并按自己的留存规则清理，不要放进自动公开同步目录。

## 验证

```sh
python contract_sensitive_detector.py --selftest
python contract_redactor.py --selftest
python -m unittest discover -s tests -p 'test_*regressions.py'
python tests/test_service_safety.py
python tests/test_launcher_safety.py
python tests/test_entity_consistency.py
python tests/test_app_e2e.py
python tests/test_output_download.py
node tests/test_save_output.js
```

测试使用虚构样例，下载测试自行生成Word，不需要作者电脑上的合同。测试服务选用空闲端口。测试脚本需要Node.js用于前端语法与保存逻辑检查；日常运行无需Node.js或AI。

## 版本与来源

源码维护在 [whatcccup/cece_legal_skills](https://github.com/whatcccup/cece_legal_skills/tree/main/001-contract-desensitizer/01-source)。[官网安装包与说明](https://legaltechcc.com/workflows/contract-desensitizer/)采用本目录 v1.2.1；每个安装包附带同版本的“源码与测试.zip”。官网同名 JSON 记录源码提交与安装包 SHA-256，可用于核对版本。SkillHub 已上架版本单独维护，不代表已更新至本版。

MIT许可见本目录 `LICENSE`。界面参考图在 `docs/images/v1.2.0-*.png`（虚构测试样例，截图保留原拍摄版本号）；最新界面以实际运行和官网展示为准。
