@echo off
REM Start QAA AirType application without showing console window
cd /d "%~dp0"

REM Install dependencies from requirements.txt
py -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo pip install failed, check Python and pip
    pause
    exit /b 1
)

REM Try to use pyw.exe first (no console window), fallback to python if not available
where pyw.exe >nul 2>&1
if %errorlevel% == 0 (
    start "" pyw.exe src/remote_server.py
) else (
    REM If pyw not available, use VBScript to hide the window
    echo Set WshShell = CreateObject("WScript.Shell") > %temp%\run_airtype.vbs
    echo WshShell.Run "python src/remote_server.py", 0, False >> %temp%\run_airtype.vbs
    cscript //nologo %temp%\run_airtype.vbs
    del %temp%\run_airtype.vbs
)

exit
