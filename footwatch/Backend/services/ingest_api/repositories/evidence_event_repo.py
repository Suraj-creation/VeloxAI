from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from services.common.config import load_settings


class EvidenceEventRepository:
    def __init__(self) -> None:
        settings = load_settings()
        self._path: Path = settings.local_data_dir / "evidence_complete.jsonl"

    def record(self, violation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        enriched = {
            "violation_id": violation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }

        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(enriched) + "\n")

        return enriched

    def latest(self, violation_id: str) -> Optional[Dict[str, Any]]:
        if not self._path.exists():
            return None

        latest_record: Optional[Dict[str, Any]] = None
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                record = line.strip()
                if not record:
                    continue
                parsed = json.loads(record)
                if parsed.get("violation_id") != violation_id:
                    continue
                latest_record = parsed

        return latest_record
