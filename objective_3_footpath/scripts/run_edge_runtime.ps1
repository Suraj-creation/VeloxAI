$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Set-Location ..

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Virtual environment not found. Run scripts/install_env.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting headless edge runtime (camera + model + preview export)" -ForegroundColor Green
.\.venv\Scripts\python.exe .\main.py --source auto --frames 0
