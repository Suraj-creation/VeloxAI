from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from services.common.config import load_settings


class CameraLiveStateRepository:
    def __init__(self) -> None:
        settings = load_settings()
        self._path: Path = settings.local_data_dir / "camera_live_state.json"

    def upsert(self, camera_id: str, payload: Dict[str, Any]) -> None:
        if self._path.exists():
            with self._path.open("r", encoding="utf-8") as handle:
                current = json.load(handle)
        else:
            current = {}

        current[camera_id] = payload

        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(current, handle, indent=2)
