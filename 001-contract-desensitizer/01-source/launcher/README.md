# 启动器 v1.2.1

先完整解压工具，准备 Python 3.9+。首次缺少依赖时需要联网；之后在本机离线运行，不需要AI。

Windows：请先解压整个 ZIP，再双击文件夹里的 `Start.vbs` 启动。不要单独移动或删除 `Start.vbs`、`Start.bat` 和 `_support` 文件夹；需要换位置时，把整个文件夹一起移动。

- Mac：双击 `mac/Contract_Redactor.app`，或使用 `mac/Contract_Redactor.command` 查看终端输出。
- Windows：双击 `windows/Contract_Redactor.vbs`，排错可运行同目录 `.bat`。
- 默认页面 `http://127.0.0.1:18800/`；服务只绑定本机。重复启动或端口由其他程序占用时会停止并提示，不强制结束任何占用者。
- 原服务通过网页“退出”停止。命令行可指定其他端口。
- 不包含打包的Python运行时，不是免环境安装程序。Windows实机仍待验证。

完整安装、数据留存与两种导出用途见上一级README。
