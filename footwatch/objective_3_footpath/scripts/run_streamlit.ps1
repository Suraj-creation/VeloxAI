$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Set-Location ..

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Virtual environment not found. Run scripts/install_env.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting Streamlit app on http://localhost:8501"
.\.venv\Scripts\python.exe -m streamlit run .\streamlit_app.py --server.headless true --browser.gatherUsageStats false --server.port 8501 --server.address localhost
