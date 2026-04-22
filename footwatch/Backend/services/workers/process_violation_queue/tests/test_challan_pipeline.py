from __future__ import annotations

import json
import shutil
from pathlib import Path

from services.common.local_violation_store import LocalViolationStore
from services.ingest_api.handlers.post_evidence_complete import handle_post_evidence_complete
from services.workers.process_violation_queue.handler import process_queue_once


def _queue_payload() -> dict:
    return {
        "violation_id": "vio-challan-001",
        "timestamp": "2026-04-23T14:23:07Z",
        "location": {
            "camera_id": "CAM-FOOTPATH-01",
            "location_name": "Whitefield Footpath Zone A",
            "gps_lat": 12.9698,
            "gps_lng": 77.7500,
        },
        "vehicle": {
            "plate_number": "KA05AB1234",
            "plate_ocr_confidence": 0.91,
            "plate_format_valid": True,
            "vehicle_class": "motorcycle",
            "estimated_speed_kmph": 18.5,
            "track_id": 201,
        },
    }


def _workspace_temp_dir(name: str) -> Path:
    root = Path(__file__).resolve().parents[4] / ".test-artifacts" / name
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_worker_marks_violation_pending_evidence_then_generates_challan(monkeypatch):
    tmp_path = _workspace_temp_dir("challan-ready")
    monkeypatch.setenv("FW_LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FW_GEMINI_API_KEY", raising=False)

    queue_path = tmp_path / "violation_queue.jsonl"
    queue_path.write_text(json.dumps(_queue_payload()) + "\n", encoding="utf-8")

    result = process_queue_once()

    assert result["processed"] == 1

    store = LocalViolationStore()
    persisted = store.get("vio-challan-001")
    assert persisted is not None
    assert persisted["challan"]["status"] == "PENDING_EVIDENCE"
    assert persisted["challan"]["download_ready"] is False

    highlighted = tmp_path / "vehicle_highlighted.jpg"
    highlighted.write_bytes(b"not-a-real-jpeg-but-present")

    evidence_result = handle_post_evidence_complete(
        "vio-challan-001",
        {
            "evidence_status": "READY",
            "evidence": {
                "vehicle_highlighted": str(highlighted),
                "full_frame": str(highlighted),
            },
        },
    )

    assert evidence_result["challan_status"] == "READY_FALLBACK"

    updated = store.get("vio-challan-001")
    assert updated is not None
    assert updated["challan"]["download_ready"] is True
    assert updated["challan"]["provider"] == "fallback"
    assert updated["challan"]["semantic_record"]["vehicle_details"]["license_plate"] == "KA05AB1234"
    assert updated["challan"]["semantic_record"]["violation_details"]["location"] == "Whitefield Footpath Zone A"
    assert (tmp_path / "challans" / "vio-challan-001" / "challan.pdf").exists()
    assert (tmp_path / "challans" / "vio-challan-001" / "challan.json").exists()


def test_worker_routes_low_confidence_violation_to_manual_review(monkeypatch):
    tmp_path = _workspace_temp_dir("challan-manual-review")
    monkeypatch.setenv("FW_LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FW_GEMINI_API_KEY", raising=False)

    payload = _queue_payload()
    payload["violation_id"] = "vio-manual-001"
    payload["vehicle"]["plate_ocr_confidence"] = 0.42

    queue_path = tmp_path / "violation_queue.jsonl"
    queue_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    result = process_queue_once()

    assert result["processed"] == 1

    persisted = LocalViolationStore().get("vio-manual-001")
    assert persisted is not None
    assert persisted["review_required"] is True
    assert persisted["challan"]["status"] == "MANUAL_REVIEW_REQUIRED"
    assert persisted["challan"]["download_ready"] is False
