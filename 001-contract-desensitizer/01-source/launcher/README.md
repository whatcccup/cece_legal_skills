# Contract Redactor 启动器

双击即用的桌面「应用」封装：自动启动本地 Python 服务，并用 **Chrome 应用窗口**打开
`http://127.0.0.1:18800/`。完全离线运行，不产生任何外联流量。

---

## 固定端口 18800

服务固定监听 `127.0.0.1:18800`。**每次双击启动器都会先结束上一次的实例**（占用 18800 的
进程、以及上一次打开的 Chrome 应用窗口），然后重新启动并重新打开页面 —— 所以反复双击
不会出现「端口被占用」或「开了一堆窗口」的问题。

---

## macOS

### 方式一：`Contract_Redactor.app`（推荐，双击即用）

双击 `mac/Contract_Redactor.app` 后会自动：

1. 结束上一次的服务进程，并关闭上一次的应用窗口；
2. 启动本地服务（完全离线，仅监听 127.0.0.1）；
3. 用 Chrome 的**应用模式窗口**打开 `http://127.0.0.1:18800/`（无地址栏、无标签页，像原生应用）；
4. 启动器本身随即退出，服务在后台常驻。

**停止服务**：点网页右上角「退出」；或再次双击本应用（会重启）。

> 未安装 Google Chrome 时，会自动改用系统默认浏览器打开。

> 首次运行前若被 macOS 拦截（「无法验证开发者」），在 Finder 里 **右键 → 打开**，
> 或执行一次：
> ```
> xattr -dr com.apple.quarantine launcher/mac/Contract_Redactor.app
> ```

### 方式二：`Contract_Redactor.command`（带终端控制台）

双击 `mac/Contract_Redactor.command`：Terminal 窗口会成为服务控制台，能看到实时日志，
按 `Ctrl-C` 结束服务。适合排查问题。

---

## Windows

### 方式一：`Contract_Redactor.vbs`（推荐，无黑窗口）

双击 `windows/Contract_Redactor.vbs`：后台完成 释放端口 → 启动服务 → 用 Chrome 应用窗口
打开页面，全程不弹出命令行窗口。

### 方式二：`Contract_Redactor.bat`（保留控制台）

双击 `windows/Contract_Redactor.bat`：窗口里显示进度；后台服务运行在一个最小化的窗口
（标题「合同脱敏 / 还原」）中。

**停止服务**：点网页右上角「退出」，或再次双击启动器。

> 需已安装 Python 3.8+ 并勾选 *Add Python to PATH*。
> 若使用 Microsoft Store 版 Python，建议改装 python.org 版本。

---

## 首次运行会自动装依赖

启动器按以下顺序寻找可用的 Python：托管 venv → 项目 `.venv` → 系统 `python3`。
若都缺少 `python-docx / pdfplumber / pypdf / reportlab / pypdfium2 / Pillow`，
会在项目下创建 `.venv` 并自动 `pip install`（约 1~2 分钟，仅第一次）。

---

## 工作目录

- macOS：`~/Library/Logs/ContractRedactor/`（`server.log` / `launcher.log`）
- 会话数据：`<项目目录>/contract_app_sessions/<sid>/`

每个会话一个独立子目录，含上传的原文、脱敏产物 `*_脱敏.docx`（映射材料已嵌入文档内部）、
还原产物 `*_还原.docx`。旧会话可随时手工删除以释放磁盘空间。

---

## 完全离线

启动器不发起任何对外网络请求。服务只绑定 `127.0.0.1`；detector 侧共享 `enforce_offline()`，
任何外联都会被阻断。

---

## 故障排查

| 现象 | 处理 |
| --- | --- |
| 双击没反应 | 先执行一次 `xattr -dr com.apple.quarantine <app>`；或改用 `.command` 看报错 |
| 「找不到 python3」 | Mac：`brew install python`；Win：从 python.org 安装并勾选 Add to PATH |
| 页面打不开 | 看 `~/Library/Logs/ContractRedactor/server.log`，或改用 `.command` 观察输出 |
| 端口 18800 被其他程序占用 | 启动器会自动结束占用者；若占用者是重要程序，请改端口后再启动 |
| 依赖装不上 | 手动执行 `python -m pip install python-docx pdfplumber pypdf reportlab pypdfium2 Pillow` |
| Mac 安全拦截 | 「系统设置 → 隐私与安全性」→ 仍要打开 |
| Windows SmartScreen 拦截 | 「更多信息 → 仍要运行」 |
