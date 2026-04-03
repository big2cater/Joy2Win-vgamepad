@echo off
chcp 65001 >nul
echo ====================================
echo Joy2Win-vgamepad 启动器
echo ====================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo [错误] 虚拟环境不存在！
    echo 请先运行：python -m venv venv
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if PyQt5 is installed
python -c "import PyQt5" 2>nul
if errorlevel 1 (
    echo [提示] 正在安装 PyQt5...
    pip install PyQt5
)

REM Check if other dependencies are installed
python -c "import bleak; import vgamepad" 2>nul
if errorlevel 1 (
    echo [提示] 正在安装其他依赖...
    pip install -r requirements-gui.txt
)

echo.
echo [信息] 启动 Joy2Win-vgamepad GUI...
echo.

REM Start the GUI
python gui.py

pause
