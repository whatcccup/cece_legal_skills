# Windows 应用启动器

`main.go` 为 Windows x64 GUI 启动入口，由标准安装程序放入应用目录。只执行随包 Python，不调用或修改系统 Python，不安装依赖。数据与日志存入当前用户的 LocalAppData，与安装目录分开；安装和卸载保留合同记录。

当前构建入口、依赖准备和 Windows 验收要求见 [Windows 安装程序构建](../windows-installer/README.md)。前一轮便携 ZIP 已停止用于新版网页下载入口。
