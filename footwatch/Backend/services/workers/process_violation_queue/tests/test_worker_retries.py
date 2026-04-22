from __future__ import annotations

from services.common.config import load_settings
from services.workers.process_violation_queue.handler import process_queue_once


def test_worker_drains_queue_after_processing():
    settings = load_settings()
    queue_path = settings.local_data_dir / "violation_queue.jsonl"
    queue_path.write_text("", encoding="utf-8")

    result = process_queue_once()

    assert result["processed"] == 0
    assert queue_path.read_text(encoding="utf-8") == ""
