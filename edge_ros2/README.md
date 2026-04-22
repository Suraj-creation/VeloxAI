# edge_ros2

Production-oriented ROS2 Humble edge runtime for Raspberry Pi 400 deployments.

The current implementation keeps the vision and tracking pipeline local on the
edge device and uses a dedicated cloud bridge to deliver backend-compatible
JSON to AWS. With the latest bridge updates, the flow now supports both:

- MQTT delivery to AWS IoT Core over TLS
- Optional HTTP mirroring to the deployed ingest API so the live frontend path works immediately

## Architecture

Logical pipeline:

1. `camera_node`
   Current package: `fw_sensor_bridge`
   Publishes camera frames and diagnostics.
2. `inference_node`
   Current package: `fw_inference_node`
   Runs two-wheeler detection.
3. `tracking_node`
   Current package: `fw_tracking_speed_node`
   Assigns track IDs and keeps object history.
4. `speed_estimation_node`
   Current package: `fw_tracking_speed_node`
   Runs the Kalman speed estimator per track.
5. `violation_detection_node`
   Current package: `fw_violation_aggregator`
   Correlates tracks, OCR, cooldown logic, and evidence output.
6. `mqtt_bridge_node`
   Current package: `fw_ros2_mqtt_bridge`
   Converts ROS messages into cloud JSON and delivers them to AWS.

Primary ROS2 topics:

- `/fw/camera/frame`
- `/fw/detect/twowheeler`
- `/fw/track/speed`
- `/fw/violation/candidate`
- `/fw/violation/confirmed`
- `/fw/health/runtime`

Cloud delivery topics:

- `footwatch/{site_id}/{camera_id}/telemetry`
- `footwatch/{site_id}/{camera_id}/violations`
- `footwatch/{site_id}/{camera_id}/live`

## Backend Payload Contract

Telemetry payload:

```json
{
  "device_id": "pi-001",
  "camera_id": "FP_CAM_001",
  "timestamp": "2026-04-23T10:00:00+00:00",
  "fps": 12.5,
  "latency_ms": 55.0,
  "status": "active"
}
```

Violation payload:

```json
{
  "violation_id": "vio-001",
  "timestamp": "2026-04-23T10:00:01+00:00",
  "location": {
    "camera_id": "FP_CAM_001",
    "location_name": "Sample Junction",
    "gps_lat": 12.9716,
    "gps_lng": 77.5946
  },
  "vehicle": {
    "plate_number": "KA05AB1234",
    "plate_ocr_confidence": 0.91,
    "plate_format_valid": true,
    "vehicle_class": "motorcycle",
    "estimated_speed_kmph": 21.0,
    "track_id": 101
  }
}
```

These payloads are what the bridge now sends to the deployed AWS ingest API.

## Raspberry Pi 400 Setup

1. Install ROS2 Humble on Ubuntu 22.04 ARM64.
2. Clone the repo onto the Pi.
3. From `edge_ros2/`, run:

```bash
bash scripts/setup.sh
```

4. Place model files into `edge_ros2/models/`:

```text
twowheeler_yolov8n.pt
lp_localiser.pt
```

5. Place AWS IoT certificates into `edge_ros2/certs/`:

```text
rootCA.pem
cert.pem
private.key
```

6. Export the backend ingest API key before launch:

```bash
export FW_INGEST_API_KEY="<your-ingest-api-key>"
```

Optional overrides:

```bash
export FW_INGEST_API_BASE_URL="https://va76meg87j.execute-api.ap-south-1.amazonaws.com/ingest"
export DEVICE_ID="pi-001"
export CAMERA_ID="FP_CAM_001"
export SITE_ID="SITE-001"
```

## Running The Pipeline

Run the full stack:

```bash
bash scripts/start.sh all
```

Run using the launch alias:

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ros2 launch fw_launch edge_pipeline.launch.py
```

Check system state:

```bash
bash scripts/start.sh status
bash scripts/smoke_test.sh
```

## Local Simulation Mode

You can validate the cloud bridge without a camera or ROS2 runtime.

Print the exact payloads:

```bash
python test_mqtt_local.py --mode mock
```

Send sample data to the deployed ingest API:

```bash
export FW_INGEST_API_KEY="<your-ingest-api-key>"
python test_mqtt_local.py --mode backend
```

Publish sample data to AWS IoT Core:

```bash
python test_mqtt_local.py --mode aws
```

## Reliability Features

- Relative certificate resolution from `edge_ros2/config/mqtt_config.json`
- Durable SQLite delivery spool in `violations/mqtt_spool.db`
- MQTT reconnect with backoff
- Replay of undelivered events after reconnect
- HTTP mirror mode for immediate backend/frontend visibility
- Best-effort live candidate stream plus durable telemetry and violations

## Testing

Run the edge test suite:

```bash
python -m pytest tests -q
```

What the tests cover:

- Payload generation against the backend contract
- HTTP ingest delivery flow
- Tracking and speed estimation behavior
- Evidence writer behavior
- End-to-end pure Python pipeline contracts

## Debugging Checklist

- `certs/` contains `rootCA.pem`, `cert.pem`, and `private.key`
- `FW_INGEST_API_KEY` is exported in the Pi shell
- `config/mqtt_config.json` points at the correct AWS IoT endpoint
- `models/` contains the detector and plate localizer weights
- `bash scripts/start.sh status` shows all ROS2 nodes
- `bash scripts/smoke_test.sh` passes local runtime checks
- `violations/mqtt_spool.db` is not growing indefinitely
- The ingest API returns `2xx` for `python test_mqtt_local.py --mode backend`
- Frontend is reachable at `https://d25zv8xa1ffqpw.cloudfront.net`
- Backend query health is reachable at `https://va76meg87j.execute-api.ap-south-1.amazonaws.com/query/health`

## Notes

- The current codebase keeps the existing `fw_*` package structure because it is already close to production-ready and test-covered.
- The cloud bridge now handles the strict backend JSON contract so the edge pipeline can stay ROS-native internally while remaining compatible with the deployed AWS backend and frontend.
