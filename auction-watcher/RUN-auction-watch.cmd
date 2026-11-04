@echo off
REM Double-click to start the Treasury auction-results watcher.
REM Waits for the next 1:00 PM ET auction, grabs the results PDF the moment
REM TreasuryDirect posts it, and opens it. Keep this window open; Ctrl+C stops it.
REM Extra options can be passed on, e.g.  RUN-auction-watch.cmd -CloseTime "11:30 AM"

set "HERE=%~dp0"
cd /d "%HERE%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%watch.ps1" %*

echo.
echo Auction watcher stopped. Press any key to close.
pause >nul
