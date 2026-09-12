@echo off
title Dedicated ATM Machine Terminal
cd /d "%~dp0"

echo ===================================================
echo   Starting Dedicated ATM Machine Terminal (UniCash)
echo ===================================================
echo.

if exist "..\ATM user\.venv\Scripts\python.exe" (
    "..\ATM user\.venv\Scripts\python.exe" server.py
) else if exist "python.exe" (
    python server.py
) else (
    py server.py
)

pause
