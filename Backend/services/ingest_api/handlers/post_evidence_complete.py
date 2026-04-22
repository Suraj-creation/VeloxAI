from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from services.common.config import load_settings


def handle_post_evidence_complete(violation_id: str, payload: Dict[str, Any]) -> dict:
    settings = load_settings()
    path: Path = settings.local_data_dir / "evidence_complete.jsonl"
    enriched = {
        "violation_id": violation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(enriched) + "\n")

    return {
        "violation_id": violation_id,
        "recorded": True,
    }
