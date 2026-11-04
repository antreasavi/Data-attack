@echo off
REM Double-click to start the Treasury auction-results watcher.
REM Opens the results page (http://localhost:8845/), waits for the next 1:00 PM ET
REM auction, and puts the results PDF on the page the moment TreasuryDirect posts it.
REM Keep this window open; Ctrl+C stops it.
REM Extra options can be passed on, e.g.  RUN-auction-watch.cmd -CloseTime "11:30 AM"

set "HERE=%~dp0"
cd /d "%HERE%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%watch.ps1" %*

echo.
echo Auction watcher stopped. Press any key to close.
pause >nul
