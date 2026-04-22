from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from services.common.config import load_settings


class LiveStateReadRepository:
    def __init__(self) -> None:
        settings = load_settings()
        self._path: Path = settings.local_data_dir / "camera_live_state.json"

    def list_all(self) -> List[Dict]:
        if not self._path.exists():
            return []

        with self._path.open("r", encoding="utf-8") as handle:
            values = json.load(handle)

        return list(values.values())
