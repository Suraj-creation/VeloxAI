param(
    [string]$PythonExe = "py -3.11"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Set-Location ..

Write-Host "[1/4] Creating virtual environment (.venv)..."
Invoke-Expression "$PythonExe -m venv .venv"

Write-Host "[2/4] Upgrading pip/setuptools/wheel..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel

Write-Host "[3/4] Installing runtime dependencies..."
.\.venv\Scripts\python.exe -m pip install -r requirements_edge.txt

Write-Host "[4/4] Verifying core imports..."
.\.venv\Scripts\python.exe -c "from ultralytics import YOLO; import cv2; import paddleocr; print('Environment OK')"

Write-Host "Setup complete. Activate with: .\\.venv\\Scripts\\Activate.ps1"
