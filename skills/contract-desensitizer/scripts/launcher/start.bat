@echo off
REM ---------------------------------------------------------------------------
REM 合同脱敏助手 · Windows 启动器
REM 双击 start.vbs（无黑窗）或直接运行本文件（可见日志）
REM 行为：自动建 .venv 并安装依赖（仅首次）→ 启动本地服务 → 打开浏览器
REM ---------------------------------------------------------------------------
setlocal
set PORT=18800
set APP_URL=http://127.0.0.1:%PORT%/
set SCRIPT_DIR=%~dp0
set PROJ_DIR=%SCRIPT_DIR%..

pushd "%PROJ_DIR%"
set PROJ_DIR=%CD%

where python >nul 2>nul || (
  echo [X] 未找到 Python，请先从 https://www.python.org/downloads/ 安装（勾选 Add to PATH）
  pause
  exit /b 1
)

if not exist "%PROJ_DIR%\.venv\Scripts\python.exe" (
  echo [.] 首次运行：创建虚拟环境...
  python -m venv "%PROJ_DIR%\.venv" || (echo [X] 创建虚拟环境失败 & pause & exit /b 1)
  echo [.] 安装依赖（约 1~2 分钟，仅此一次）...
  "%PROJ_DIR%\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  "%PROJ_DIR%\.venv\Scripts\python.exe" -m pip install --quiet -r "%PROJ_DIR%\requirements.txt" || (
    echo [X] 依赖安装失败，请检查网络后重试 & pause & exit /b 1
  )
)
set PY=%PROJ_DIR%\.venv\Scripts\python.exe

if not exist "%PROJ_DIR%\sessions" mkdir "%PROJ_DIR%\sessions"

echo [.] 项目目录：%PROJ_DIR%
echo [.] 启动服务（完全离线，仅监听 127.0.0.1）...
start "" /B "%PY%" "%PROJ_DIR%\contract_app_server.py" --host 127.0.0.1 --port %PORT% --workdir "%PROJ_DIR%\sessions"

echo [.] 等待服务就绪...
ping -n 6 127.0.0.1 >nul
start "" %APP_URL%
echo [OK] 已打开 %APP_URL%
echo     停止服务：网页右上角「退出」。
timeout /t 5 >nul
popd
endlocal
