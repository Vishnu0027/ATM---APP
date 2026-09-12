# PowerShell Launcher for Dedicated ATM Machine Terminal
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Starting Dedicated ATM Machine Terminal (UniCash)" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

if (Test-Path "..\ATM user\.venv\Scripts\python.exe") {
    & "..\ATM user\.venv\Scripts\python.exe" server.py
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python server.py
} else {
    py server.py
}
