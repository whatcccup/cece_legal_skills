# Windows 标准安装程序构建

NSIS 的 `setup.nsi` 将独立 Python 环境、依赖和应用程序打包为标准安装向导。默认按当前用户安装到 `%LOCALAPPDATA%\Programs\ContractRedactor`，创建桌面和开始菜单入口，登记 Windows 卸载入口；不修改系统 Python。

数据在 `%LOCALAPPDATA%\ContractRedactor\Data`，与程序目录分离。卸载不删除用户数据。运行期间通过本机命名互斥量阻止重复启动或覆盖安装，不结束其他程序。

从官网仓库根目录，准备好前一轮的 `work/windows-portable-build`（Go、Python embed ZIP、Windows wheels）后：

```sh
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 work/windows-portable-build/go/bin/go build -trimpath -ldflags='-s -w -H=windowsgui' -o work/windows-portable-build/ContractRedactor.exe packages/contract-desensitizer/launcher/windows-exe/main.go
python scripts/tools/package-contract-windows-installer.py
```

组装脚本会调用已有 Python payload 组装器，再调用本机 `makensis`（本轮3.13），仅产生本地预览 EXE 和 SHA-256/文件清单，不提交、推送或发布。旧便携 ZIP 只保留恢复依据，网页不再引用。

验证要求：先通过 NSIS 编译和7-Zip完整性/解包比对；再在 Windows 10/11 x64 上完成真实安装、中文用户名、桌面和开始菜单启动、首次断网、无系统Python、已有Python不受影响、重复启动、端口占用、虚构Word/PDF/TXT处理、退出、更新和卸载保留数据测试。Mac只能完成构建及静态检查，不能替代这组实机验收。
