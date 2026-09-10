@echo off
REM ===========================================================================
REM  Contract Redactor . Windows 启动器
REM  双击 Contract_Redactor.bat 即可（不想看到黑窗口请双击 Contract_Redactor.vbs）
REM
REM  行为：
REM    1. 释放固定端口 18800（结束上一次的服务进程）
REM    2. 关掉上一次打开的 Chrome 应用窗口
REM    3. 启动本地服务（完全离线，只监听 127.0.0.1）
REM    4. 用 Chrome 的「应用模式」窗口打开 http://127.0.0.1:18800/
REM ===========================================================================

setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>nul

set "PORT=18800"
set "APP_URL=http://127.0.0.1:%PORT%/"
set "TITLE=合同脱敏 / 还原"

REM ---- 定位项目根（本文件在 launcher\windows\ 下，项目根是上两级）----
cd /d "%~dp0"
set "SELF_DIR=%CD%"
set "PROJ_DIR="
if exist "%SELF_DIR%\..\..\contract_app_server.py" set "PROJ_DIR=%SELF_DIR%\..\.."
if not defined PROJ_DIR (
    if exist "%~dp0contract_app_server.py" set "PROJ_DIR=%~dp0"
)
if not defined PROJ_DIR (
    if exist "%~dp0..\contract_app_server.py" set "PROJ_DIR=%~dp0.."
)
if not defined PROJ_DIR (
    echo [X] 找不到 contract_app_server.py，请把启动器放在项目的 launcher\windows\ 目录下。
    pause
    exit /b 1
)
pushd "%PROJ_DIR%"
set "PROJ_DIR=%CD%"
popd

echo.
echo  ================================================================
echo    合同脱敏 / 还原   Contract Redactor
echo    完全离线运行 . 所有处理都在本机完成
echo  ================================================================
echo.

REM ------------------------------------------------------------- 1. 找 Python
set "PY="
set "MANAGED=%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if exist "%MANAGED%" set "PY=%MANAGED%"

if not defined PY if exist "%PROJ_DIR%\.venv\Scripts\python.exe" set "PY=%PROJ_DIR%\.venv\Scripts\python.exe"

if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    echo [X] 找不到 Python 3.x，请先安装：https://www.python.org/downloads/
    echo     安装时请勾选 [Add Python to PATH]
    pause
    exit /b 1
)
echo  . Python: %PY%

REM ------------------------------------------------------------- 2. 依赖自检
%PY% -c "import docx, pdfplumber, pypdf, reportlab, pypdfium2, PIL" >nul 2>nul
if errorlevel 1 (
    echo  . 首次运行：正在创建运行环境并安装依赖，请稍候 1~2 分钟 ...
    if not exist "%PROJ_DIR%\.venv" (
        %PY% -m venv "%PROJ_DIR%\.venv"
        if errorlevel 1 (
            echo [X] 创建虚拟环境失败。
            pause
            exit /b 1
        )
    )
    set "PY=%PROJ_DIR%\.venv\Scripts\python.exe"
    "%PY%" -m pip install --upgrade pip >nul 2>nul
    "%PY%" -m pip install python-docx pdfplumber pypdf reportlab pypdfium2 Pillow
    if errorlevel 1 (
        echo [X] 依赖安装失败，请手动执行：
        echo     "%PY%" -m pip install python-docx pdfplumber pypdf reportlab pypdfium2 Pillow
        pause
        exit /b 1
    )
)

REM ------------------------------------------------------------- 3. 释放端口
echo  . 检查端口 %PORT% ...
REM 3.1 结束占用该端口的进程
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:"TCP.*:%PORT% .*LISTENING"') do (
    echo    - 结束占用进程 PID %%p
    taskkill /PID %%p /T /F >nul 2>nul
)
REM 3.2 兜底：结束其它残留的服务进程（wmic 在新版 Windows 已移除，改用 PowerShell）
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*contract_app_server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul

REM 3.3 关掉上一次打开的 Chrome 应用窗口（使用独立 profile，不会影响用户自己的 Chrome）
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter ""Name='chrome.exe'"" | Where-Object { $_.CommandLine -like '*ContractRedactor*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul

REM ------------------------------------------------------------- 4. 起服务
set "WORKDIR=%PROJ_DIR%\contract_app_sessions"
if not exist "%WORKDIR%" mkdir "%WORKDIR%"
set "SERVER_LOG=%WORKDIR%\server.log"

echo  . 启动本地服务 ...
start "%TITLE%" /min cmd /c "cd /d "%PROJ_DIR%" && "%PY%" "%PROJ_DIR%\contract_app_server.py" --host 127.0.0.1 --port %PORT% --workdir "%WORKDIR%" > "%SERVER_LOG%" 2>&1"

REM ------------------------------------------------------------- 5. 等服务就绪
set /a TRIED=0
:wait
set /a TRIED+=1
if !TRIED! GTR 80 (
    echo [X] 服务未能在 20 秒内启动，日志：%SERVER_LOG%
    type "%SERVER_LOG%"
    pause
    exit /b 1
)
%PY% -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%PORT%/health',timeout=1).status==200 else 1)" >nul 2>nul
if errorlevel 1 (
    ping -n 1 -w 250 127.0.0.1 >nul 2>nul
    goto :wait
)

REM ------------------------------------------------------------- 6. 打开界面
set "CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if defined CHROME (
    echo  . 用 Chrome 应用窗口打开 %APP_URL%
    set "PROFILE=%LocalAppData%\ContractRedactor\chrome-profile"
    if not exist "!PROFILE!" mkdir "!PROFILE!"
    start "" "%CHROME%" --app="%APP_URL%" --user-data-dir="!PROFILE!" --no-first-run --no-default-browser-check
) else (
    echo  . 未检测到 Chrome，使用默认浏览器打开
    start "" "%APP_URL%"
)

echo.
echo  ---------------------------------------------------------------
echo    服务已启动： %APP_URL%
echo    服务窗口已最小化到任务栏，标题为「%TITLE%」
echo    需要停止服务：点网页右上角「退出」，或再次双击本启动器
echo  ---------------------------------------------------------------
echo.
timeout /t 4 >nul 2>nul
endlocal
exit /b 0
