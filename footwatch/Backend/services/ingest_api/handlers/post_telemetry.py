from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from services.common.validators import validate_payload
from services.ingest_api.repositories.camera_live_state_repo import CameraLiveStateRepository


def handle_post_telemetry(payload: Dict[str, Any], repo: CameraLiveStateRepository) -> dict:
    validate_payload(payload, "telemetry_ingest.json")

    ttl_seconds = 180
    expires_at = int((datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).timestamp())
    enriched = {
        **payload,
        "last_seen_ts": payload.get("timestamp"),
        "expires_at": expires_at,
    }

    repo.upsert(payload["camera_id"], enriched)
    return {"camera_id": payload["camera_id"], "expires_at": expires_at}
