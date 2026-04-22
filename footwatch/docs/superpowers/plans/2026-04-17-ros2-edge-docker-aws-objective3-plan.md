# ROS2 Edge + Docker + AWS Objective 3 Plan (Robust)

Goal: Build a Docker-first development workflow on your main system that exactly mirrors Raspberry Pi edge runtime behavior, then deploy only required runtime artifacts to Pi for stable Objective 3 enforcement operations and AWS dashboard integration.

Core idea alignment:
- Local machine is the primary development and debugging environment (VS Code + Copilot).
- Docker provides architecture-faithful simulation for Pi edge runtime.
- Raspberry Pi receives only runtime-focused code, configs, models, and compose manifests.
- ROS2 handles edge-device communication and orchestration.
- MQTT broker path sends normalized events to AWS where dashboard services consume them.

---

## 1) Scope and System Boundaries

In scope:
- Edge inference for Objective 3 stages on Pi (detect, track, speed, plate OCR, evidence).
- ROS2 pub/sub graph for device data and inference events.
- MQTT bridge from ROS2 topics to AWS IoT Core topics.
- Cloud ingestion path and dashboard visibility.
- Dockerized local simulation and CI checks.

Out of scope:
- Full cloud retraining pipeline.
- Sending raw continuous video streams to cloud.

Non-negotiables from Objective 3:
- Edge-first processing.
- Offline tolerance and retry/spool behavior.
- Persist only confirmed violations and evidence records.
- Calibration-driven speed estimation and conservative enforcement thresholds.

---

## 2) Target Architecture (3-Lane)

Lane A: Local Dev Simulation (Laptop)
- Runs ARM64-compatible Docker stack for ROS2 and inference services.
- Uses recorded clips or local USB camera.
- Executes same ROS2 topics, contracts, and MQTT payload schema used in production.

Lane B: Edge Production (Raspberry Pi)
- Runs the same container images (linux/arm64).
- Mounts camera device, config, models, and violations volume.
- Publishes only normalized telemetry/events to cloud.

Lane C: Cloud Application (AWS)
- MQTT ingress through AWS IoT Core.
- Rule actions to Lambda/API storage path.
- Existing backend serves dashboard APIs.

---

## 3) Repository Strategy (Two-Codebase Model)

Codebase 1: Existing app repository
- Keep current AWS backend + frontend dashboard.
- Add ingestion contract adapters and dashboards for ROS2/MQTT events.

Codebase 2: New edge repository (recommended)
- Contains ROS2 workspace and Docker orchestration for edge runtime.
- Keeps edge concerns isolated from cloud UI concerns.

Suggested edge repository structure:
- edge_ros2/
  - docker/
    - Dockerfile.edge
    - Dockerfile.sim
    - compose.dev.yml
    - compose.pi.yml
  - ros2_ws/
    - src/
      - fw_sensor_bridge/
      - fw_inference_node/
      - fw_tracking_speed_node/
      - fw_plate_ocr_node/
      - fw_violation_aggregator/
      - fw_ros2_mqtt_bridge/
      - fw_health_node/
      - fw_msgs/
  - config/
    - camera_lab.json
    - speed_calibration.json
    - footpath_roi.json
    - thresholds.json
  - models/
  - scripts/
    - run_dev.ps1
    - run_pi.sh
    - smoke_test.sh
  - tests/
    - contract/
    - integration/
    - performance/

---

## 4) ROS2 Topic and Message Contract Plan

Design principle:
- Separate raw sensor frames from event outputs.
- Keep MQTT payloads compact and versioned.

Core ROS2 topics:
- /fw/camera/frame
- /fw/detect/twowheeler
- /fw/track/speed
- /fw/plate/ocr
- /fw/violation/candidate
- /fw/violation/confirmed
- /fw/health/runtime

MQTT publish topics (AWS IoT):
- footwatch/{site_id}/{camera_id}/live
- footwatch/{site_id}/{camera_id}/violation
- footwatch/{site_id}/{camera_id}/health

Required payload fields:
- schema_version
- event_id (idempotency key)
- device_id
- camera_id
- ts_utc
- event_type
- speed_kmph
- class_name
- confidence
- plate_text
- ocr_confidence
- gps_lat
- gps_lng
- evidence_uri (optional)

---

## 5) Docker-First Development Model

Primary objective:
- Ensure local Docker behavior equals Pi runtime behavior.

Build approach:
- Build multi-arch images with buildx.
- Validate linux/arm64 images in local simulation before Pi rollout.

Container set:
- ros_core (ROS2 base runtime)
- inference_node
- tracking_speed_node
- ocr_node
- violation_aggregator
- ros2_mqtt_bridge
- health_monitor

Must-have runtime options on Pi:
- host networking for ROS2 DDS discovery.
- explicit ROS_DOMAIN_ID per deployment.
- camera device mapping /dev/video0.
- persistent volumes for config, models, violations, logs.

---

## 6) Objective 3 Stage Mapping to Nodes

Stage 1 Two-wheeler detection:
- Node: fw_inference_node
- Output: detections with confidence and bbox

Stage 2 Direct full-frame enforcement flow:
- Node: fw_violation_aggregator
- Logic: no polygon gating in decision path unless site explicitly enables

Stage 3 Tracking and speed estimation:
- Node: fw_tracking_speed_node
- Input: detections
- Output: track_id, speed, motion confidence

Stage 4 Plate localization:
- Node: fw_plate_ocr_node (localizer submodule)

Stage 5 Plate enhancement:
- Node: fw_plate_ocr_node (enhancement submodule)

Stage 6 OCR:
- Node: fw_plate_ocr_node (OCR submodule + regex validator)

Stage 7 Evidence package and challan event:
- Node: fw_violation_aggregator
- Output: confirmed violation event + evidence bundle metadata

---

## 7) Phase Plan (Robust and Incremental)

Phase 0 Foundations (2-3 days)
- Finalize event contract and topic naming.
- Define config schema and defaults.
- Add architectural decision records.

Exit gate:
- Contract document approved.
- Local schema validator passing.

Phase 1 Edge ROS2 Skeleton in Docker (3-4 days)
- Create ROS2 workspace and minimal nodes.
- Run local pub/sub and health status.
- Add compose.dev.yml and compose.pi.yml.

Exit gate:
- Local simulation publishes health and sample events.

Phase 2 Inference Pipeline Integration (4-6 days)
- Integrate existing Objective 3 pipeline into nodes.
- Wire detection->tracking->OCR->violation topics.
- Add failure modes (waiting_frame, signal_flat, camera_disconnect).

Exit gate:
- Reproducible violation event on sample clips.
- No pipeline crash under camera reconnect scenarios.

Phase 3 MQTT Bridge and Cloud Ingestion (3-5 days)
- Implement ROS2-to-MQTT bridge with retry buffer.
- Connect to AWS IoT Core and route to backend ingestion.
- Add idempotency checks on cloud ingest.

Exit gate:
- At-least-once delivery with dedup safe in backend.
- Dashboard receives live + confirmed events.

Phase 4 Pi Production Hardening (3-4 days)
- Resource tuning for Pi 4.
- Start-time checks for camera/model/config availability.
- Add watchdog and auto-restart policies.

Exit gate:
- 8-hour soak test on Pi with stable memory and bounded CPU.

Phase 5 Validation and Release (2-3 days)
- End-to-end test from ESP32 input to dashboard render.
- Accuracy and latency acceptance test against Objective 3 metrics.
- Produce runbook and rollback guide.

Exit gate:
- Signed operational checklist.

---

## 8) Testing Strategy (What You Asked to Fix and Keep Stable)

Test layers:
- Unit: message mappers, calibration math, idempotency key generation.
- Contract: ROS2 message and MQTT JSON schema validation.
- Integration: multi-container local stack test with recorded video.
- Performance: target fps and latency on local arm64 emulation and Pi.
- Soak: long-run stability with reconnect and broker outage simulation.

Critical test cases:
- camera unavailable at startup
- camera disconnect mid-run
- flat/white frame signal
- OCR low confidence fallback
- MQTT temporary outage and replay
- duplicate event publish and backend dedup

Acceptance baseline:
- edge loop remains alive under all above failures
- no unbounded queue growth
- dashboard receives consistent event stream

---

## 9) Deployment Workflow You Specifically Need

Development loop on your system:
- Edit code in VS Code + Copilot.
- Run Docker dev stack locally.
- Run ROS2 graph tests and integration tests.
- Build linux/arm64 images.

Promotion to Pi:
- Push image to registry.
- Pull image on Pi.
- Sync only runtime artifacts:
  - compose.pi.yml
  - config files
  - models
  - edge node packages
- Start stack and run smoke tests.

Why this matches your core ask:
- You do not need full dev toolchain on Pi.
- You do not need full monorepo on Pi.
- Behavior parity is maintained via identical images and contracts.

---

## 10) AWS Integration Plan

Broker:
- AWS IoT Core as central MQTT entry.

Rules/actions:
- live topic -> lightweight state update path
- violation topic -> evidence + durable record path
- health topic -> monitoring and alerts

Backend bridge options:
- Option A: IoT Rule -> Lambda -> existing Backend APIs
- Option B: IoT Rule -> DynamoDB/S3 directly + Query API aggregation

Recommendation:
- Start with Option A for consistency with existing API contracts and auth handling.

Dashboard updates:
- Existing frontend reads cloud APIs for history and current state.
- Optional real-time websocket integration later after stability baseline is reached.

---

## 11) Resource Budget for Pi 4

Practical limits:
- Use 640x360 or 960x540 processing for live loop.
- Keep target FPS around 8-12 for stable thermal behavior.
- Trigger OCR only for violation candidates.
- Save only violation evidence images.

Storage guidance:
- If your device is truly 4GB storage, upgrade storage medium before production.
- Minimum practical storage is 16GB, recommended 32GB or SSD for logs and model updates.

---

## 12) Risk Register and Mitigations

Risk: ROS2 DDS discovery instability in containers
- Mitigation: host networking + CycloneDDS + fixed domain ids

Risk: camera driver differences between laptop and Pi
- Mitigation: enforce camera probe checks and startup diagnostics in container

Risk: MQTT outages cause data loss
- Mitigation: local persistent retry spool with TTL and replay policy

Risk: low-light OCR quality
- Mitigation: conservative confidence thresholds and manual review queue for low confidence

Risk: schema drift between edge and cloud
- Mitigation: versioned schema and contract tests in CI

---

## 13) Immediate Action Checklist (Next 7 Days)

Day 1
- Freeze event schema v1 and topic taxonomy.
- Create new edge_ros2 repository skeleton.

Day 2
- Add ROS2 minimal nodes and local compose.dev stack.

Day 3
- Add inference wrapper around existing Objective 3 runtime modules.

Day 4
- Add tracking/speed and OCR nodes, with synthetic test fixtures.

Day 5
- Add MQTT bridge and AWS IoT test topic flow.

Day 6
- Run integration + failure scenario tests.

Day 7
- Build arm64 image, deploy to Pi, run soak test and dashboard verification.

---

## 14) Definition of Done

Done means all of the following are true:
- Local Docker simulation matches Pi runtime behavior for core scenarios.
- Pi runs edge inference + ROS2 communication + MQTT bridge reliably.
- AWS receives and stores event stream with no duplicate corruption.
- Dashboard displays live state and confirmed violations from cloud data.
- Runbooks exist for start, stop, update, recovery, and rollback.
