from __future__ import annotations

import json
from pathlib import Path

from services.common.config import load_settings
from services.workers.process_violation_queue.services.alert_publisher import publish_alert
from services.workers.process_violation_queue.services.violation_normalizer import normalize_violation
from services.workers.process_violation_queue.services.violation_persister import ViolationPersister


def process_queue_once() -> dict:
    settings = load_settings()
    queue_path: Path = settings.local_data_dir / "violation_queue.jsonl"

    if not queue_path.exists():
        return {"processed": 0}

    lines = queue_path.read_text(encoding="utf-8").splitlines()
    persister = ViolationPersister()
    processed = 0

    for line in lines:
        if not line.strip():
            continue
        payload = json.loads(line)
        normalized = normalize_violation(payload)
        persister.persist(normalized)
        publish_alert(normalized)
        processed += 1

    queue_path.write_text("", encoding="utf-8")
    return {"processed": processed}


if __name__ == "__main__":
    result = process_queue_once()
    print(json.dumps(result))
