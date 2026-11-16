@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==========================================
echo 构建 WinUHid 用户态 DLL
echo ==========================================
echo.
echo 说明：只会编译 WinUHid.dll 和 WinUHidDevs.dll 两个用户态库，
echo       不需要 WDK，也不需要重新安装驱动。
echo.

set "SRC=%~dp0WinUHid-src"
set "OUT=%~dp0.."

rem ---------- 1. 定位 MSBuild ----------
set "MSB="
for %%P in (
  "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe"
  "C:\Program Files\Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\MSBuild.exe"
  "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\MSBuild\Current\Bin\MSBuild.exe"
  "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
) do if exist %%P set "MSB=%%~P"

if not defined MSB (
    echo [错误] 未找到 MSBuild。
    echo.
    echo 请安装 Visual Studio 2022 或 Build Tools，并勾选：
    echo     「使用 C++ 的桌面开发」工作负载
    echo.
    pause
    exit /b 1
)
echo [信息] MSBuild: %MSB%

rem ---------- 2. 获取源码 ----------
if not exist "%SRC%\WinUHid.sln" (
    echo [信息] 正在下载 WinUHid 源码...
    git clone --depth 1 https://github.com/lurebat/WinUHid.git "%SRC%"
    if errorlevel 1 (
        echo [错误] 克隆失败。请确认已安装 Git 且能访问 GitHub。
        pause
        exit /b 1
    )
) else (
    echo [信息] 已存在源码目录，跳过下载
)

rem ---------- 3. 编译两个用户态 DLL ----------
echo.
echo [信息] 编译 WinUHid.dll ...
"%MSB%" "%SRC%\WinUHid\WinUHid.vcxproj" /p:Configuration=Release /p:Platform=x64 /v:minimal /nologo
if errorlevel 1 goto :failed

echo.
echo [信息] 编译 WinUHidDevs.dll ...
"%MSB%" "%SRC%\WinUHidDevs\WinUHidDevs.vcxproj" /p:Configuration=Release /p:Platform=x64 /v:minimal /nologo
if errorlevel 1 goto :failed

rem ---------- 4. 复制到程序目录 ----------
rem Each project writes to <Project>\build\Release\x64 (WinUHidCppProps.props),
rem not to a shared root build folder.
echo.
call :copy_dll "WinUHid" "WinUHid.dll"
call :copy_dll "WinUHidDevs" "WinUHidDevs.dll"

echo.
echo 若上面显示「已复制」，重启 Joy2Win 后应看到：
echo   INFO - WinUHid mouse available ^(driver interface ...^)
echo   INFO - Raw Input virtual mouse created
echo   INFO - Mouse output: WinUHid ^(Raw Input^)
echo.
pause
exit /b 0

:copy_dll
set "PROJ=%~1"
set "FILE=%~2"
if exist "%SRC%\%PROJ%\build\Release\x64\%FILE%" (
    copy /y "%SRC%\%PROJ%\build\Release\x64\%FILE%" "%OUT%\%FILE%" >nul
    if not errorlevel 1 (
        echo [完成] %FILE% 已复制到程序目录
        goto :eof
    )
)
if exist "%SRC%\%PROJ%\x64\Release\%FILE%" (
    copy /y "%SRC%\%PROJ%\x64\Release\%FILE%" "%OUT%\%FILE%" >nul
    if not errorlevel 1 (
        echo [完成] %FILE% 已复制到程序目录
        goto :eof
    )
)
if exist "%SRC%\%PROJ%\Release\%FILE%" (
    copy /y "%SRC%\%PROJ%\Release\%FILE%" "%OUT%\%FILE%" >nul
    if not errorlevel 1 (
        echo [完成] %FILE% 已复制到程序目录
        goto :eof
    )
)
echo [警告] 未找到编译产物 %FILE%，请检查上面的编译输出。
goto :eof

:failed
echo.
echo [错误] 编译失败。常见原因：
echo   1. Visual Studio 没有安装「使用 C++ 的桌面开发」工作负载
echo   2. 缺少 Windows SDK（VS 安装器里可勾选）
echo   3. 源码目录被占用或权限不足
echo.
echo 修复方法：打开 Visual Studio Installer，修改 Build Tools，
echo 勾选「使用 C++ 的桌面开发」，再重新运行本脚本。
echo.
pause
exit /b 1
