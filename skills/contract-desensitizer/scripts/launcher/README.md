# 启动器说明

| 平台 | 文件 | 用法 |
|---|---|---|
| macOS / Linux | `start.sh` | 双击（macOS 可改名为 `启动.command` 后双击）或终端 `bash start.sh` |
| Windows | `start.vbs` | 双击，无黑窗；想看日志就双击 `start.bat` |

启动器会自动完成：

1. 找带依赖的 Python；找不到就新建 `.venv` 并安装 `requirements.txt`（仅首次，约 1~2 分钟）
2. 释放 18800 端口、结束上一次的服务进程
3. 启动 `contract_app_server.py`（完全离线，只监听 `127.0.0.1`）
4. 健康检查通过后打开 `http://127.0.0.1:18800/`

停止：点击网页右上角「退出」，或在终端按 Ctrl-C（前台模式）。

> macOS 首次双击若提示「无法验证开发者」：右键该文件 → 打开 → 确认即可。
