from __future__ import annotations

from typing import Any, Dict, Optional

from services.common.errors import ApiError
from services.common.idempotency import payload_hash
from services.common.validators import validate_payload
from services.ingest_api.repositories.idempotency_repo import IdempotencyRepository
from services.ingest_api.repositories.violation_queue_repo import ViolationQueueRepository


def handle_post_violation(
    payload: Dict[str, Any],
    idempotency_key: Optional[str],
    queue_repo: ViolationQueueRepository,
    idempotency_repo: IdempotencyRepository,
) -> dict:
    validate_payload(payload, "violation_ingest.json")

    if not idempotency_key:
        raise ApiError(400, "missing_idempotency_key", "Idempotency key header is required")

    digest = payload_hash(payload)
    if idempotency_repo.seen(idempotency_key, digest):
        return {
            "queued": False,
            "duplicate": True,
            "violation_id": payload["violation_id"],
        }

    idempotency_repo.remember(idempotency_key, digest)
    queue_repo.enqueue(payload)

    return {
        "queued": True,
        "duplicate": False,
        "violation_id": payload["violation_id"],
    }
