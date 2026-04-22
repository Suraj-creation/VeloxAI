from __future__ import annotations

import importlib
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from services.common.local_violation_store import LocalViolationStore


def _workspace_temp_dir(name: str) -> Path:
    root = Path(__file__).resolve().parents[4] / ".test-artifacts" / name
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_challan_download_serves_pdf(monkeypatch):
    tmp_path = _workspace_temp_dir("challan-download")
    monkeypatch.setenv("FW_LOCAL_DATA_DIR", str(tmp_path))

    pdf_path = tmp_path / "ready-challan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    store = LocalViolationStore()
    store.upsert(
        {
            "violation_id": "vio-download-001",
            "timestamp": "2026-04-23T14:23:07Z",
            "location": {"camera_id": "CAM-FOOTPATH-01"},
            "vehicle": {"plate_number": "KA05AB1234"},
            "violation_status": "CONFIRMED_AUTO",
            "evidence_status": "READY",
            "created_at": "2026-04-23T14:23:07Z",
            "updated_at": "2026-04-23T14:23:07Z",
            "challan": {
                "status": "READY_FALLBACK",
                "download_ready": True,
                "pdf_path": str(pdf_path),
                "json_path": None,
            },
        }
    )

    import services.query_api.app as query_app_module

    query_app_module = importlib.reload(query_app_module)
    client = TestClient(query_app_module.app)

    response = client.get("/v1/violations/vio-download-001/challan-download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert "vio-download-001-challan.pdf" in response.headers["content-disposition"]
