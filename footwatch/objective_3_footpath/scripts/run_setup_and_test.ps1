$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Set-Location ..

$rtspSource = $env:RTSP_SOURCE
$clipsDir = $env:EVAL_CLIPS_DIR

Write-Host "[1/5] Installing environment"
PowerShell -ExecutionPolicy Bypass -File .\scripts\install_env.ps1

Write-Host "[2/5] Initializing config files"
.\.venv\Scripts\python.exe .\scripts\init_configs.py

Write-Host "[3/5] Downloading pretrained models"
.\.venv\Scripts\python.exe .\scripts\download_models.py

Write-Host "[4/5] Running smoke unit checks"
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q .\tests\smoke_test.py

Write-Host "[5/5] Running runtime smoke loop (15 frames)"
.\.venv\Scripts\python.exe .\main.py --source 0 --frames 15

if ($rtspSource) {
	Write-Host "[RTSP] Running RTSP smoke loop (60 frames)"
	.\.venv\Scripts\python.exe .\main.py --source $rtspSource --frames 60
}

if ($clipsDir) {
	Write-Host "[EVAL] Running multi-clip evaluation pass (up to 180 clips)"
	.\.venv\Scripts\python.exe .\scripts\evaluate_180_clips.py --clips-dir $clipsDir --max-clips 180 --frames-per-clip 120
}
