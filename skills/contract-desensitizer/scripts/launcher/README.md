# 启动器说明

跨平台只有一个入口，Windows / macOS / Linux 通用：

```bash
python scripts/launcher/start.py                 # 启动并自动打开浏览器
python scripts/launcher/start.py --foreground    # 前台运行，日志留在终端，Ctrl-C 结束
```

启动器会自动完成：

1. 找带依赖的 Python；找不到就新建 `.venv` 并安装 `requirements.txt`（仅首次，约 1~2 分钟）
2. 释放 18800 端口、结束上一次的服务进程
3. 启动 `contract_app_server.py`（完全离线，只监听 `127.0.0.1`）
4. 健康检查通过后打开 `http://127.0.0.1:18800/`

停止：点击网页右上角「退出」，或在终端按 Ctrl-C（前台模式）。

想做桌面快捷方式：macOS 把 `python <绝对路径>/start.py` 存成 `.command` 文件，
Windows 存成 `.bat`——这类文件放在技能包里会被平台上架校验拦截，所以请在你自己电脑上创建。
