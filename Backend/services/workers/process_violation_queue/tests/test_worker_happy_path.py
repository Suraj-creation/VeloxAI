from __future__ import annotations

import json

from services.common.config import load_settings
from services.workers.process_violation_queue.handler import process_queue_once


def test_worker_processes_queue_messages():
    settings = load_settings()
    queue_path = settings.local_data_dir / "violation_queue.jsonl"

    queue_path.write_text(
        json.dumps(
            {
                "violation_id": "vio-worker-1",
                "timestamp": "2026-01-01T12:00:00Z",
                "location": {"camera_id": "FP_CAM_001"},
                "vehicle": {
                    "plate_number": "KA05AB1234",
                    "plate_ocr_confidence": 0.9,
                    "vehicle_class": "motorcycle",
                    "estimated_speed_kmph": 20.0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = process_queue_once()

    assert result["processed"] >= 1
