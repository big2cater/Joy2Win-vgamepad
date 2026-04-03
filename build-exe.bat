@echo off
chcp 65001 >nul
echo ====================================
echo Joy2Win-vgamepad 打包工具
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

REM Install PyInstaller
echo [信息] 正在安装 PyInstaller...
pip install pyinstaller

REM Clean previous builds
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo.
echo [信息] 开始打包 Joy2Win-vgamepad...
echo.

REM Run PyInstaller
pyinstaller --noconfirm --onefile --windowed --name "Joy2Win-vgamepad" --icon="logo.ico" gui.py

if exist "dist\Joy2Win-vgamepad.exe" (
    echo.
    echo ====================================
    echo 打包成功！
    echo 可执行文件位置：dist\Joy2Win-vgamepad.exe
    echo ====================================
    echo.
    
    REM Copy config files
    echo [信息] 复制配置文件...
    copy "config.ini" "dist\config.ini"
    copy "config-example.ini" "dist\config-example.ini"
    copy "requirements-gui.txt" "dist\requirements-gui.txt"
    
    echo.
    echo [提示] 请在 dist 目录中运行 Joy2Win-vgamepad.exe
    echo.
) else (
    echo.
    echo [错误] 打包失败！
    echo.
)

pause
