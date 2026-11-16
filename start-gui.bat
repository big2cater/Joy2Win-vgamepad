@echo off
chcp 65001 >nul
setlocal EnableExtensions

rem Always work from this script's own folder. Double-clicking normally sets
rem the CWD here, but shortcuts, IDE runners and "run as administrator" can
rem start elsewhere, which made the relative "venv" check fail even though the
rem folder exists.
cd /d "%~dp0"

echo ====================================
echo Joy2Win-vgamepad 启动器
echo ====================================
echo.

set "VENV_PY=%~dp0venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [错误] 虚拟环境不存在！
    echo 查找路径: %VENV_PY%
    echo 当前目录: %CD%
    echo.
    echo 请在本目录执行以下命令创建环境（需要 Python 3.12）：
    echo     py -3.12 -m venv venv
    echo     venv\Scripts\python.exe -m pip install -r requirements-gui.txt
    echo.
    pause
    exit /b 1
)

rem Use the venv interpreter directly instead of activate.bat: it is immune to
rem PATH ordering and to a parent shell that already has another python first.
"%VENV_PY%" -c "import PyQt5, bleak, vgamepad" 2>nul
if errorlevel 1 (
    echo [提示] 依赖不完整，正在安装...
    "%VENV_PY%" -m pip install -r "%~dp0requirements-gui.txt"
)

echo [信息] 解释器: %VENV_PY%
echo [信息] 启动 Joy2Win-vgamepad GUI...
echo.

"%VENV_PY%" "%~dp0gui.py"

echo.
echo [信息] 程序已退出。
pause
