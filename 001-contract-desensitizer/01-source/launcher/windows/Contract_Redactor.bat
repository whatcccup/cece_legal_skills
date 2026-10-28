@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>nul
set "PORT=18800"
set "PROJ_DIR=%~dp0_support"
if not exist "%PROJ_DIR%\contract_app_server.py" set "PROJ_DIR=%~dp0..\.."
cd /d "%PROJ_DIR%"
set "PROJ_DIR=%CD%"
if not exist "contract_app_server.py" goto missing_project
netstat -ano | findstr /R /C:"TCP.*:%PORT% .*LISTENING" >nul
if not errorlevel 1 goto port_busy
set "PY="
set "PY_ARGS="
if exist ".venv\Scripts\python.exe" set "PY=%PROJ_DIR%\.venv\Scripts\python.exe"
if defined PY goto check_deps
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto check_deps
where py >nul 2>nul
if not errorlevel 1 set "PY=py"
if defined PY set "PY_ARGS=-3"
if not defined PY goto missing_python
:check_deps
"%PY%" %PY_ARGS% -c "import sys; assert sys.version_info >= (3,9); import docx,pdfplumber,pypdf,reportlab,pypdfium2,PIL" >nul 2>nul
if not errorlevel 1 goto launch
"%PY%" %PY_ARGS% -m venv ".venv"
if errorlevel 1 goto install_failed
set "PY=%PROJ_DIR%\.venv\Scripts\python.exe"
set "PY_ARGS="
"%PY%" -m pip install -r "%PROJ_DIR%\requirements.txt"
if errorlevel 1 goto install_failed
:launch
set "WORKDIR=%PROJ_DIR%\contract_app_sessions"
if not exist "%WORKDIR%" mkdir "%WORKDIR%"
start "合同脱敏工具" /min "%PY%" %PY_ARGS% "%PROJ_DIR%\contract_app_server.py" --host 127.0.0.1 --port %PORT% --workdir "%WORKDIR%" --open-browser
exit /b 0
:port_busy
echo 端口 %PORT% 已被占用。先打开 http://127.0.0.1:%PORT%/ 查看是否为已运行的工具。
echo 如果是旧工具，点右上角退出后重试；如果是其他程序，请让AI检查并选择其他端口。不会结束其他进程。
pause
exit /b 1
:missing_project
echo 找不到工具源码，请完整解压 ZIP 后再启动。
pause
exit /b 1
:missing_python
echo 请先安装 Python 3.9 或以上版本，并勾选 Add Python to PATH。
pause
exit /b 1
:install_failed
echo Python 环境或依赖安装失败，请保留上方错误信息进行排查。
pause
exit /b 1
