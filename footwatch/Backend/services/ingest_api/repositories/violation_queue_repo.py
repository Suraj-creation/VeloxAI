from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from services.common.config import load_settings


class ViolationQueueRepository:
    def __init__(self) -> None:
        settings = load_settings()
        self._path: Path = settings.local_data_dir / "violation_queue.jsonl"

    def enqueue(self, payload: Dict[str, Any]) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
