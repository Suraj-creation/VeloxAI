# Footwatch Edge Runtime — `edge_ros2` (Native)

**Production-grade ROS 2 Humble edge inference system for Objective 3 Footpath Enforcement.**

This repository has been optimized to run completely natively (without Docker) on both **Ubuntu (x86_64)** engineering test systems and **Raspberry Pi 400 (ARM64)** edge deployments.

---

## System Overview

```
[Camera /video0 or RTSP]
         │
  [fw_sensor_bridge] ── publish header.frame_id ──► /fw/camera/frame
         │
         ├──► [fw_inference_node]       ── Stage 1 YOLOv8 detection ──► /fw/detect/twowheeler
         │
         ├──► [fw_tracking_speed_node]  ── ByteTrack + Kalman ──► /fw/track/speed
         │
         ├──► [fw_plate_ocr_node]       ── LP localise + CLAHE + PaddleOCR ──► /fw/plate/ocr
         │
         └──► [fw_violation_aggregator] ── evidence bundle + challan ──► /fw/violation/confirmed
                   │
              [fw_ros2_mqtt_bridge] ── SQLite spool + at-least-once ──► AWS IoT Core MQTT
                   │
              [fw_health_node] ── metrics + watchdog ──► /fw/health/runtime → Prometheus
```

---

## Getting Started

### 1. One-Time Setup
Run the setup script on a fresh Ubuntu Humble or Raspberry Pi system to install dependencies and build the workspace.
```bash
cd edge_ros2
bash scripts/setup.sh
```
*Note: This script will install Python dependencies, configure testing folders, and run `colcon build --symlink-install`.*

### 2. Prepare Models
Download and place the following AI models into the `models/` folder:
- `twowheeler_yolov8n.pt`
- `lp_localiser.pt`

### 3. Run the Stack Locally
To start all 7 ROS2 nodes at once, use the unified `start.sh` script, which wraps the ROS2 launch framework:
```bash
bash scripts/start.sh all
```

**(Optional)** Run a local Mosquitto MQTT broker for testing:
```bash
bash scripts/start.sh mosquitto
```

### 4. Verify System 
In a new terminal window, execute the smoke test to verify all nodes are communicating, taking snapshots of topics, checking CPU health, and verifying SQLite bridges:
```bash
bash scripts/smoke_test.sh
```

---

## Repository Structure

```
edge_ros2/
├── ros2_ws/src/
│   ├── fw_launch/               # Master launch file package
│   ├── fw_msgs/                 # Custom ROS 2 interfaces
│   ├── fw_sensor_bridge/        # Camera ingress & UUID tagging
│   ├── fw_inference_node/       # Stage 1: Pipeline
│   ├── fw_tracking_speed_node/  # Stage 3: Kalman speed
│   ├── fw_plate_ocr_node/       # Stages 4/5/6: Enhancement + OCR
│   ├── fw_violation_aggregator/ # Stage 7: Event creation
│   ├── fw_ros2_mqtt_bridge/     # AWS proxy and durable spools
│   └── fw_health_node/          # Device vitals export
├── config/
│   ├── camera_lab.json          # Device ID, resolution
│   ├── speed_calibration.json   # Scale factors
│   ├── thresholds.json          # NLP confidences
│   └── mqtt_config.json         # AWS IoT endpoint + Cert flags 
├── scripts/
│   ├── setup.sh                 # Environment setup and build
│   ├── start.sh                 # CLI abstraction over launch files
│   ├── smoke_test.sh            # E2E test
│   └── local_mqtt_to_aws_mock.py# Dev bridge to test AWS -> Backend calls
├── tests/                       # Unit/Integration testing suite
├── requirements.txt             # Unified Python dependencies
└── README.md
```

---

## ROS2 Topic Contract

All node correlations use `msg.header.frame_id` dynamically assigned by `fw_sensor_bridge`.

| Topic | Publisher | QoS | Rate | Note |
|---|---|---|---|---|
| `/fw/camera/frame` | `fw_sensor_bridge` | BEST_EFFORT | Video FPS | `sensor_msgs/CompressedImage` |
| `/fw/detect/twowheeler` | `fw_inference_node` | RELIABLE | Batched | Filters cars/pedestrians |
| `/fw/track/speed` | `fw_tracking_speed_node` | RELIABLE | Synchronous | Issues unique Box IDs |
| `/fw/plate/ocr` | `fw_plate_ocr_node` | RELIABLE | Async | Yields highest prob license |
| `/fw/violation/confirmed` | `fw_violation_aggregator` | RELIABLE | Event | Assembles evidence payloads |
| `/fw/health/runtime` | `fw_health_node` | RELIABLE | 10s intervals | HW telemetry |

---

## MQTT Topic Contract (AWS IoT Core)

| MQTT Topic | Trigger | QoS | Content |
|---|---|---|---|
| `footwatch/{site_id}/{camera_id}/violation` | Confirmed challan | 1 | Full violation payload schema v1 |
| `footwatch/{site_id}/{camera_id}/live` | Candidate detection | 0 | Live bounding box event |
| `footwatch/{site_id}/{camera_id}/health` | Heartbeat | 0 | Device health metrics |

---

## AWS IoT Deployment
1. Connect via AWS Console and create "Thing" policy for `fp-edge-*`.
2. Save credentials to `certs/`:
   - `root-CA.crt`
   - `device.cert.pem`
   - `device.private.key`
3. Update `config/mqtt_config.json` configuration target.
4. The edge node will spool offline packets to `violations/mqtt_spool.db` and auto-replay when WAN link resumes.

## Tests (Unit & Edge)
Pytest validates node logic, while skipping heavy integrations transparently.

```bash
cd edge_ros2
pytest tests/ -v
```

_Apache-2.0 — Footwatch Edge Team_
