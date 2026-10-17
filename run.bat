@echo off
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python was not found on PATH. Install Python 3.9+ and try again.
    pause
    exit /b 1
)

rem Desktop overlay window: waits until WOS below is ready.
rem Extra arguments are passed to it, e.g.  run.bat --browser
start "WOS Overlay UI" /min python overlay\main.py %*

rem The normal WOS terminal, with the overlay connection enabled.
python start.py --overlay
