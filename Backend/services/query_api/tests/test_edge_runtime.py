from __future__ import annotations

from fastapi.testclient import TestClient

from services.query_api.app import app


client = TestClient(app)


def test_get_edge_runtime_status_returns_payload():
    response = client.get("/v1/edge/live-preview")
    assert response.status_code == 200

    payload = response.json()
    assert "request_id" in payload
    assert "runtime" in payload["data"]


def test_get_edge_config_returns_resolved_values():
    response = client.get("/v1/edge/config")
    assert response.status_code == 200

    payload = response.json()
    assert "request_id" in payload
    assert "resolved" in payload["data"]


def test_put_edge_config_persists_and_returns_updated_config():
    response = client.put(
        "/v1/edge/config",
        json={
            "cameraId": "FP_CAM_TEST",
            "locationName": "Test Junction",
            "targetFps": 12,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["resolved"]["cameraId"] == "FP_CAM_TEST"
    assert payload["data"]["resolved"]["locationName"] == "Test Junction"
    assert payload["data"]["resolved"]["targetFps"] == 12


def test_get_edge_preview_frame_returns_image_or_not_found():
    response = client.get("/v1/edge/live-preview/frame")
    assert response.status_code in {200, 404}
