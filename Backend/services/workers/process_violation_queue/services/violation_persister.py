from __future__ import annotations

import json
from pathlib import Path

from services.common.config import load_settings


class ViolationPersister:
    def __init__(self) -> None:
        settings = load_settings()
        self._path: Path = settings.local_data_dir / "violations.jsonl"

    def persist(self, payload: dict) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
