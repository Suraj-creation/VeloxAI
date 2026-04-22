from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


def _write_if_missing(path: Path, data: dict) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    _write_if_missing(
        CONFIG_DIR / "footpath_roi.json",
        {
            "footpath_roi": [[200, 700], [1700, 700], [1800, 1000], [100, 1000], [200, 700]],
            "buffer_zone_expand_px": 15,
            "camera_id": "FP_CAM_001",
            "location_name": "Sample Junction",
            "gps_lat": 12.9716,
            "gps_lng": 77.5946,
            "calibration_date": "2026-04-09",
        },
    )
    _write_if_missing(
        CONFIG_DIR / "speed_calibration.json",
        {
            "pixels_per_metre": 47.0,
            "camera_fps": 15,
            "calibration_date": "2026-04-09",
        },
    )
    _write_if_missing(
        CONFIG_DIR / "dashboard.json",
        {
            "mqtt_host": "mqtt.dashboard.local",
            "mqtt_port": 1883,
            "mqtt_topic": "footpath/violations",
        },
    )
    print("Config files initialized.")


if __name__ == "__main__":
    main()
