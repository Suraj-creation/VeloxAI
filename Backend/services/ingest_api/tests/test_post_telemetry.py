from __future__ import annotations

from fastapi.testclient import TestClient

from services.ingest_api.app import app


def test_post_telemetry_accepts_valid_payload():
    client = TestClient(app)
    response = client.post(
        "/v1/telemetry",
        headers={"x-api-key": "dev-key"},
        json={
            "camera_id": "FP_CAM_001",
            "timestamp": "2026-01-01T12:00:00Z",
            "fps": 12.5,
            "latency_ms": 82.0,
            "status": "online",
            "location_name": "Sample Junction",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["camera_id"] == "FP_CAM_001"
