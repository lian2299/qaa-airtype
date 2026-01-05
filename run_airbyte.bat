@echo off
REM Start QAA AirType application without showing console window
cd /d "%~dp0"

REM Try to use pythonw.exe first (no console window), fallback to python if not available
where pythonw.exe >nul 2>&1
if %errorlevel% == 0 (
    start "" pythonw.exe src/remote_server.py
) else (
    REM If pythonw not available, use VBScript to hide the window
    echo Set WshShell = CreateObject("WScript.Shell") > %temp%\run_airtype.vbs
    echo WshShell.Run "python src/remote_server.py", 0, False >> %temp%\run_airtype.vbs
    cscript //nologo %temp%\run_airtype.vbs
    del %temp%\run_airtype.vbs
)

exit
