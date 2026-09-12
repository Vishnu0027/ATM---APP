@echo off
title Multi-Bank Cardless ATM
cd /d "%~dp0"

echo ===================================================
echo   Starting Multi-Bank Cardless ATM (UniCash)
echo ===================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    py run.py
)

pause
