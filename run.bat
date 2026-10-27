@echo off
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python was not found on PATH. Install Python 3.11+ and try again.
    pause
    exit /b 1
)

rem Desktop overlay window: waits until Auralis below is ready.
rem Extra arguments are passed to it, e.g.  run.bat --browser
start "Auralis Overlay UI" /min python overlay\main.py %*

rem The normal Auralis terminal, with the overlay connection enabled.
python start.py --overlay %*
