from __future__ import annotations

from fastapi.testclient import TestClient

from services.query_api.app import app


def test_list_violations_returns_ok_payload():
    client = TestClient(app)
    response = client.get("/v1/violations?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert "request_id" in payload
    assert "items" in payload["data"]


def test_list_violations_supports_filters():
    client = TestClient(app)
    response = client.get("/v1/violations?limit=10&status=CONFIRMED_AUTO&class=motorcycle")

    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload["data"]


def test_get_violations_summary_returns_ok_payload():
    client = TestClient(app)
    response = client.get("/v1/violations/summary")

    assert response.status_code == 200
    payload = response.json()
    assert "request_id" in payload
    assert "total_violations" in payload["data"]


def test_get_alerts_returns_ok_payload():
    client = TestClient(app)
    response = client.get("/v1/alerts?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert "request_id" in payload
    assert "items" in payload["data"]
