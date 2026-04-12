from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    local = root / ".local"
    local.mkdir(parents=True, exist_ok=True)

    camera_state = {
        "FP_CAM_001": {
            "camera_id": "FP_CAM_001",
            "status": "online",
            "fps": 12.4,
            "latency_ms": 83.1,
            "last_seen_ts": "2026-01-01T12:00:00Z",
            "expires_at": 1893456000,
        }
    }

    (local / "camera_live_state.json").write_text(json.dumps(camera_state, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
