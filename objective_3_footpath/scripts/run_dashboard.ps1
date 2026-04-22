$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Set-Location ..

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Virtual environment not found. Run scripts/install_env.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting live dashboard on http://localhost:8502" -ForegroundColor Green
.\.venv\Scripts\python.exe -m streamlit run .\dashboard.py --server.headless true --browser.gatherUsageStats false --server.port 8502 --server.address localhost
