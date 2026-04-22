from __future__ import annotations

from fastapi.testclient import TestClient

from services.query_api.app import app


def test_get_live_cameras_returns_ok_payload():
    client = TestClient(app)
    response = client.get("/v1/live/cameras")

    assert response.status_code == 200
    payload = response.json()
    assert "request_id" in payload
    assert "data" in payload
    assert "items" in payload["data"]
