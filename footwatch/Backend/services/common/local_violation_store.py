from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.common.config import load_settings


def deep_merge_dict(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(base)

    for key, value in patch.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = deep_merge_dict(existing, value)
            continue
        merged[key] = value

    return merged


class LocalViolationStore:
    def __init__(self) -> None:
        settings = load_settings()
        self._path: Path = settings.local_data_dir / "violations.jsonl"

    def _load_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []

        items: List[Dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                record = line.strip()
                if not record:
                    continue
                items.append(json.loads(record))

        return items

    def _write_all(self, items: List[Dict[str, Any]]) -> None:
        with self._path.open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item) + "\n")

    def list_all(self) -> List[Dict[str, Any]]:
        items = self._load_all()
        items.sort(
            key=lambda item: str(item.get("updated_at") or item.get("timestamp") or item.get("created_at") or ""),
            reverse=True,
        )
        return items

    def get(self, violation_id: str) -> Optional[Dict[str, Any]]:
        for item in self.list_all():
            if item.get("violation_id") == violation_id:
                return item
        return None

    def upsert(self, payload: Dict[str, Any]) -> None:
        violation_id = payload.get("violation_id")
        items = [item for item in self._load_all() if item.get("violation_id") != violation_id]
        items.append(payload)
        self._write_all(items)

    def merge_patch(self, violation_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        current = self.get(violation_id)
        if current is None:
            return None

        merged = deep_merge_dict(current, patch)
        self.upsert(merged)
        return merged
