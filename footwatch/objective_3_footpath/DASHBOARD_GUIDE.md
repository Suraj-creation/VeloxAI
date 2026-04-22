# Objective 3 — Complete Live Enforcement &amp; Dashboard Setup

This guide walks you through setting up and running the **complete Objective 3 system**: live footpath violation detection with real-time dashboard monitoring.

## Architecture Overview

```
┌─────────────────────┐
│  Laptop Camera      │
│   (USB Webcam)      │
└──────────┬──────────┘
           │
           v
┌─────────────────────────────────────────┐
│  Enforcement App (Streamlit)            │
│  Port: http://localhost:8501            │
│  • Live camera feed                     │
│  • Two-wheeler detection                │
│  • ROI boundary checking                │
│  • Speed estimation  (ByteTrack)        │
│  • Plate detection + OCR                │
│  • Evidence generation                  │
│  • Violation file storage               │
│  • Metrics export to .metrics.json      │
└──────────┬──────────────────────────────┘
           │
           ├─ violations/ (JSON + images)
           │
           ├─ .metrics.json (live FPS, stats)
           │
           v
┌─────────────────────────────────────────┐
│  Dashboard (Streamlit)                  │
│  Port: http://localhost:8502            │
│  • Live system metrics (FPS, latency)   │
│  • Violation history & statistics       │
│  • Vehicle class breakdown              │
│  • Hourly trend charts                  │
│  • Evidence photo viewer                │
│  • Individual violation details         │
│  • Plate validation rates               │
│  • Speed distribution                   │
└─────────────────────────────────────────┘
```

---

## Quick Start (Recommended for Testing)

### Option A: Run Both Apps in Separate Terminals

**Terminal 1 — Start the Enforcement App:**

```powershell
cd c:\Users\Govin\Desktop\IOT\objective_3_footpath
PowerShell -ExecutionPolicy Bypass -File .\scripts\run_streamlit.ps1
```

Wait for it to say:
```
You can now view your Streamlit app in your browser.
URL: http://localhost:8501
```

Then open: **http://localhost:8501**

In the sidebar:
1. Select "Footpath Enforcement" mode
2. Set Camera Index to your laptop camera (usually 0)
3. Ensure "Enable Plate Detection + OCR" is toggled ON
4. Click **Start**

---

**Terminal 2 — Start the Dashboard:**

```powershell
cd c:\Users\Govin\Desktop\IOT\objective_3_footpath
PowerShell -ExecutionPolicy Bypass -File .\scripts\run_dashboard.ps1
```

Wait for:
```
You can now view your Streamlit app in your browser.
URL: http://localhost:8502
```

Then open: **http://localhost:8502**

---

### Result

- **Enforcement App** (8501): Live camera feed with real-time detection and evidence capture
- **Dashboard** (8502): Live statistics, violation history, evidence viewer, and trends

The dashboard updates every 10 seconds to show:
- Real-time FPS and latency
- Total violations recorded
- Unique plates detected
- Vehicle class breakdown
- Speed statistics
- OCR confidence rates
- Evidence images

---

## What Each Component Does

### Enforcement App (streamlit_app.py)

**Continuous workflow:**

1. **Live Camera Capture** (persistent background thread)
   - Never closes the webcam
   - Streams frames seamlessly

2. **Detection & ROI Check**
   - YOLOv8n two-wheeler detection
   - Filters only objects inside the footpath ROI

3. **Multi-Object Tracking + Speed**
   - ByteTrack ID continuity
   - Pixel-to-meter speed estimation
   - Cooldown per vehicle (60s) to avoid duplicate challan


4. **Plate Detection + OCR** (if moving violation confirmed)
   - YOLOv8n licence plate localizer
   - PaddleOCR with Indian LP validation
   - OCR voting (3 augmentations for confidence)

5. **Evidence Packaging**
   - Saves full frame with annotations
   - Saves raw + enhanced plate crops
   - Generates JSON metadata
   - Stores in `violations/` directory

6. **Metrics Export**
   - Writes `.metrics.json` every frame
   - Contains FPS, latency, detection count, camera health

---

### Dashboard (dashboard.py)

**Live display of**:

- **System Health** (from `.metrics.json`):
  - Inference FPS
  - Per-frame latency (ms)
  - Camera failures & reconnects
  - Live event count

- **Violation Analytics** (from `violations/` directory):
  - Total violations (last 24h)
  - Unique plates caught
  - Average speed & max speed
  - Plate validation success rate
  - Average OCR confidence

- **Charts**:
  - Vehicle class distribution (bar chart)
  - Plate validation split (pie chart)
  - Violations over time (hourly line chart)

- **Evidence Viewer**:
  - Full frame with bounding boxes
  - Raw plate crop
  - Enhanced plate crop (CLAHE + sharpening)
  - Violation metadata JSON

---

## Configuration Files

Located in `config/`:

### footpath_roi.json
```json
{
  "footpath_roi": [[200, 700], [1700, 700], [1800, 1000], [100, 1000], [200, 700]],
  "camera_id": "FP_CAM_001",
  "location_name": "Sample Junction",
  "gps_lat": 12.9716,
  "gps_lng": 77.5946
}
```
- **Adjust the polygon** to match your camera's footpath region
- Right-click in VS Code on a white area on your camera frame to calibrate

### speed_calibration.json
```json
{
  "pixels_per_metre": 47.0,
  "camera_fps": 15
}
```
- **pixels_per_metre**: Place a 1-metre ruler on the footpath and measure how many pixels it spans
- **camera_fps**: Frame rate your camera is set to (visible in enforcement app)

---

## Understanding Violation Records

Each violation saved in `violations/{timestamp}_{plate}_{id}/` contains:

### violation_metadata.json
```json
{
  "violation_id": "uuid-here",
  "timestamp": "2026-04-10T09:05:12.123456",
  "location": {
    "camera_id": "FP_CAM_001",
    "location_name": "Sample Junction",
    "gps_lat": 12.9716,
    "gps_lng": 77.5946
  },
  "vehicle": {
    "plate_number": "KA05AB1234",
    "plate_ocr_confidence": 0.89,
    "plate_format_valid": true,
    "vehicle_class": "motorcycle",
    "estimated_speed_kmph": 18.5,
    "track_id": 42
  },
  "violation_type": "FOOTPATH_ENCROACHMENT",
  "fine_amount_inr": 500,
  "system": {
    "model_version": "YOLOv8n + ByteTrack + PaddleOCR",
    "pushed_to_dashboard": false
  }
}
```

### Evidence Files
- `evidence_frame.jpg` — Full wide-angle frame with violation box annotated
- `plate_crop_raw.jpg` — Raw extracted plate region
- `plate_crop_enhanced.jpg` — Enhanced plate (CLAHE + sharpening for OCR)
- `thumbnail.jpg` — Small preview

---

## Dashboard Features Explained

### Live System Status (Yellow Alert Box)
Appears only when enforcement app is running. Shows:
- **Inference FPS**: Detections per second (target: 10–15 on laptop)
- **Latency (ms)**: Time per frame (target: 60–100 ms)
- **Detected Objects**: Count of vehicles in frame this cycle
- **Camera Failures**: Consecutive read errors (should stay at 0)
- **Reconnects**: Number of times camera was auto-recovered

### Violation Analytics
- **Total Violations**: Unique e-Challans generated
- **Unique Plates**: Count of distinct vehicles caught
- **Avg Speed**: Average violation speed (should be > 5 km/h to trigger)
- **Valid Plates %**: Percentage with correct Indian LP format
- **Avg OCR Confidence**: Model confidence on plate reads (0.0–1.0)

### Charts
1. **Vehicle Class Distribution**: Breakdown by motorcycle / bicycle / scooter
2. **Plate Validation**: Split between valid format vs invalid
3. **Violations Over Time**: Hourly trend (useful for peak violation analysis)

### Violation Details & Evidence
- Select any violation from dropdown
- View full JSON metadata
- Inspect evidence images (full frame, raw plate, enhanced plate)
- Review all extracted fields

---

## Troubleshooting

### Dashboard shows "Enforcement app not running"
- Make sure enforcement app is started first (terminal 1)
- Check URL is http://localhost:8501 and shows live camera

### Camera keeps flickering / closing in enforcement app
- This is **now fixed** with persistent background capture
- If still flickering: try different camera index (0, 1, 2) in the app

### Plate OCR confidence always low (&lt; 0.6)
- Ensure room has good lighting
- Plate must be at least 80 pixels wide on camera
- Adjust ROI or camera angle for clearer plate view
- Check `config/speed_calibration.json` is correct (affects crop size)

### No violations appearing in dashboard
- Check enforcement app is set to "Footpath Enforcement" mode
- Verify ROI polygon is covering the footpath area in the camera view
- Make sure a vehicle is actually inside the ROI moving faster than 5 km/h
- Check a violation was triggered: `violations/` folder should have timestamped subdirectory

### Can't find violations folder in dashboard
- Keep the enforcement app running; it continuously writes to `violations/`
- Refresh dashboard manually (button in UI)

---

## Data Available for Analysis

The complete system now captures and stores:

Per violation:
- Unique violation ID &amp; timestamp
- GPS coordinates of the enforcement location
- Detected plate number + OCR confidence
- Vehicle class (motorcycle / bicycle / scooter / etc)
- Estimated speed (based on multi-frame tracking)
- Track persistence ID (to avoid duplicate frames)
- Evidence images (3 variants: raw, enhanced, full-frame)
- Fine amount &amp; legal section applied
- System/model metadata

Metrics exported live:
- Per-frame inference FPS
- Inference latency in milliseconds
- Detection count per frame
- Camera health (failures &amp; reconnects)
- Real-time event stream

### Dashboard provides computed analytics:
- Time-series violations by hour
- Unique vehicle count
- Plate validation success rate
- Average vehicle speed distribution
- Vehicle class breakdown
- OCR confidence distribution

---

## Advanced: Running on Raspberry Pi / Edge Device

To deploy on a Raspberry Pi:

1. Install Python 3.11: `sudo apt install python3.11`
2. Run setup script: `PowerShell -File scripts/install_env.ps1`
3. Optional: Install Coral USB accelerator for 4× faster inference
4. Configure systemd service to auto-start enforcement app on boot
5. Point dashboard port (8502) to the Pi's IP address on your network

Example systemd service (`/etc/systemd/system/footpath-enforcement.service`):
```ini
[Unit]
Description=Objective 3 Footpath Enforcement
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/objective_3_footpath
ExecStart=/home/pi/objective_3_footpath/.venv/bin/python -m streamlit run streamlit_app.py --server.port 8501
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then: `sudo systemctl enable footpath-enforcement && sudo systemctl start footpath-enforcement`

---

## Next Steps

1. ✅ Run enforcement app + camera live
2. ✅ Open dashboard to monitor violations
3. ⏭️ [Optional] Set up MQTT push to police backend
4. ⏭️ [Optional] Deploy to Raspberry Pi for 24/7 operation
5. ⏭️ [Optional] Fine-tune models on real site-specific data

---

*Objective 3 — Footpath Violation Detection & Auto-Enforcement*
*Complete live system with continuous enforcement + analytics dashboard*
