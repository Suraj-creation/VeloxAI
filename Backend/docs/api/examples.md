# API Examples

## Ingest Telemetry

```http
POST /v1/telemetry
x-api-key: dev-key
Content-Type: application/json

{
  "camera_id": "FP_CAM_001",
  "timestamp": "2026-01-01T12:00:00Z",
  "fps": 12.4,
  "latency_ms": 83.1,
  "status": "online"
}
```

## Ingest Violation

```http
POST /v1/violations
x-api-key: dev-key
x-idempotency-key: vio-001
Content-Type: application/json

{
  "violation_id": "vio-001",
  "timestamp": "2026-01-01T12:00:00Z",
  "location": { "camera_id": "FP_CAM_001" },
  "vehicle": {
    "plate_number": "KA05AB1234",
    "plate_ocr_confidence": 0.88,
    "vehicle_class": "motorcycle",
    "estimated_speed_kmph": 19.2
  }
}
```
