from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from services.ingest_api.app import app


def _sample_violation() -> dict:
    return {
        "violation_id": "vio-001",
        "timestamp": "2026-01-01T12:00:00Z",
        "location": {
            "camera_id": "FP_CAM_001",
            "location_name": "Sample Junction",
            "gps_lat": 12.9,
            "gps_lng": 77.5,
        },
        "vehicle": {
            "plate_number": "KA05AB1234",
            "plate_ocr_confidence": 0.88,
            "plate_format_valid": True,
            "vehicle_class": "motorcycle",
            "estimated_speed_kmph": 18.4,
            "track_id": 42,
        },
    }


def test_post_violation_idempotent_duplicate_returns_duplicate_flag():
    client = TestClient(app)
    unique_id = uuid.uuid4().hex[:10]
    payload = _sample_violation()
    payload["violation_id"] = f"vio-{unique_id}"

    headers = {
        "x-api-key": "dev-key",
        "x-idempotency-key": f"idem-vio-{unique_id}",
    }

    first = client.post("/v1/violations", headers=headers, json=payload)
    second = client.post("/v1/violations", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["duplicate"] is False
    assert second.json()["data"]["duplicate"] is True
