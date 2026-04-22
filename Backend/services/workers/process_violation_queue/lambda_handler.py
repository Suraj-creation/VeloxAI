from __future__ import annotations

import json
from typing import Any, Dict, List

from services.workers.process_violation_queue.handler import process_queue_once
from services.workers.process_violation_queue.services.alert_publisher import publish_alert
from services.workers.process_violation_queue.services.violation_normalizer import normalize_violation
from services.workers.process_violation_queue.services.violation_persister import ViolationPersister


def _process_records(records: List[Dict[str, Any]]) -> int:
    persister = ViolationPersister()
    processed = 0

    for record in records:
        raw_body = record.get("body")
        if raw_body is None:
            continue

        payload = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
        normalized = normalize_violation(payload)
        persister.persist(normalized)
        publish_alert(normalized)
        processed += 1

    return processed


def handler(event: Dict[str, Any], _context: Any) -> Dict[str, int]:
    records = event.get("Records", []) if isinstance(event, dict) else []

    if records:
        return {"processed": _process_records(records)}

    return process_queue_once()
