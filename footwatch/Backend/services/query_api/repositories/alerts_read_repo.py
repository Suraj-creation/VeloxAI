from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.common.config import load_settings


class AlertsReadRepository:
    def __init__(self, path: Optional[Path] = None) -> None:
        settings = load_settings()
        self._path = path or Path(settings.local_data_dir) / "alerts.jsonl"

    def list_all(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []

        items: List[Dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                items.append(json.loads(line))

        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return items[:limit]
