$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Set-Location ..

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Virtual environment not found. Run scripts/install_env.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting edge-to-backend sync loop (default ingest: http://127.0.0.1:8000)" -ForegroundColor Green
.\.venv\Scripts\python.exe .\scripts\push_to_backend.py
