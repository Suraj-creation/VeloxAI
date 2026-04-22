from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from services.common.config import load_settings


class IdempotencyRepository:
    def __init__(self) -> None:
        settings = load_settings()
        self._path: Path = settings.local_data_dir / "idempotency.json"

    def _load(self) -> Dict[str, str]:
        if not self._path.exists():
            return {}
        with self._path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save(self, payload: Dict[str, str]) -> None:
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def seen(self, key: str, digest: str) -> bool:
        values = self._load()
        return values.get(key) == digest

    def remember(self, key: str, digest: str) -> None:
        values = self._load()
        values[key] = digest
        self._save(values)
