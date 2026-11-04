@echo off
REM Stops Auction Watch, including a copy running in the background with no window.
set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%stop.ps1"
timeout /t 3 >nul
