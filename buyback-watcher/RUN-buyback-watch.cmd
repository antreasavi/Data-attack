@echo off
REM Double-click this to start Buyback Watch.
REM Runs the watcher + the alert page in this one window, opens your browser,
REM and bypasses the PowerShell execution policy so you change no settings.
REM Keep this window open. Close it (or press Ctrl+C) to stop.

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*

echo.
echo Buyback Watch stopped. Press any key to close.
pause >nul
