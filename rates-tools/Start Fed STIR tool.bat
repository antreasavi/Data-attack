@echo off
rem Starts the Fed STIR scenario tool: the engine + web page (browser), then the always-on-top strip.
cd /d "%~dp0"
start "Fed STIR engine" /min python run_stirtool.py
timeout /t 3 /nobreak >nul
start "" pythonw run_strip.py
