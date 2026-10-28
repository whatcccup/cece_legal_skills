# 自带 Python 的 macOS App 构建

Apple/Intel 分包，不依赖系统 Python 或 Rosetta 来运行对应的原生版本。Python 3.13.12 来自 Astral python-build-standalone（通过 uv 下载），各自包含对应架构的13个依赖；许可随运行时和各 dist-info 一起保留。

Go启动器只调用App内Python，`-I`隔离外部Python配置，bootstrap显式添加包内引擎目录。数据和规则在当前用户 `Library/Application Support/ContractRedactor`，不写App内部，支持移动App及升级保留规则；文件锁避免重复启动，不杀其他进程。

输入位于官网 `work/mac-bundled-build`：
- `python/cpython-3.13.12-macos-{aarch64,x86_64}-none`：`uv python install --install-dir work/mac-bundled-build/python --no-bin` 的两架构分发。
- `wheels-{arm64,x86_64}`：pip download的macOS12对应架构、cp313二进制依赖。各文件与SHA记录在下载包同名JSON。
- `launcher-{arm64,amd64}`：用Go交叉编译 `main.go`，GOOS=darwin、对应GOARCH、CGO_ENABLED=0。

运行官网 `scripts/tools/package-contract-mac-app.py` 会创建新构建目录、临时签名并验证、用ditto保留App结构和符号链接打ZIP，不提交或发布。ad-hoc签名不是Developer ID签名/公证，不能消除Gatekeeper提示。

实际验证应从ZIP解压副本执行，移动至含空格目录后，用无系统Python的PATH及无效PYTHONHOME/PYTHONPATH做隔离测试。再验证GUI启动、规则复制/保留、DOCX/PDF/TXT处理、退出、已有服务不被结束及不同架构依赖。Intel/Rosetta通过不等于Intel物理机或macOS12实机通过。
