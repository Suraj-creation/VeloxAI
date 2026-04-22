# Objective 3 Runtime Setup (No Retraining)

This project sets up a no-retraining edge runtime using pretrained models:
- https://huggingface.co/Ultralytics/YOLOv8?utm_source=chatgpt.com
- https://huggingface.co/yasirfaizahmed/license-plate-object-detection?utm_source=chatgpt.com

## Quick start (PowerShell)

1. Open PowerShell in this folder.
2. Run:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\scripts\run_setup_and_test.ps1
```

## Manual setup

```powershell
PowerShell -ExecutionPolicy Bypass -File .\scripts\install_env.ps1
.\.venv\Scripts\python.exe .\scripts\init_configs.py
.\.venv\Scripts\python.exe .\scripts\download_models.py
.\.venv\Scripts\python.exe -m pytest -q .\tests\smoke_test.py
.\.venv\Scripts\python.exe .\main.py --source 0 --frames 60
```

## Notes

- If your Python launcher defaults to 3.14, the install script still forces Python 3.11.
- If camera index 0 is unavailable, pass a video file path to --source.
- Calibrate config values in config/footpath_roi.json and config/speed_calibration.json before deployment.

## Streamlit Webcam App

Use the laptop camera with live object detection and optional plate OCR.
Inside the app sidebar, select **General Objects (YOLOv8n)** to detect most common object classes.

```powershell
PowerShell -ExecutionPolicy Bypass -File .\\scripts\\run_streamlit.ps1
```

Then open:

http://localhost:8501

## Backend Integration Sync (Local E2E)

When running local Backend ingest API on port 8000, you can push telemetry and saved violations
from this edge workspace into Backend using:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\scripts\run_backend_sync.ps1
```

For a one-time sync run:

```powershell
.\.venv\Scripts\python.exe .\scripts\push_to_backend.py --once
```
