from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.common.config import load_settings


class ViolationsReadRepository:
    def __init__(self) -> None:
        settings = load_settings()
        self._path: Path = settings.local_data_dir / "violations.jsonl"

    def _load_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []

        items: List[Dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                items.append(json.loads(line))

        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return items

    def list_all(self, limit: int = 50, filters: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        items = self._load_all()

        if filters:
            camera_id = filters.get("camera_id")
            plate = filters.get("plate")
            vehicle_class = filters.get("class")
            status = filters.get("status")
            from_ts = filters.get("from")
            to_ts = filters.get("to")

            def matches(item: Dict[str, Any]) -> bool:
                location = item.get("location", {})
                vehicle = item.get("vehicle", {})

                if camera_id and location.get("camera_id") != camera_id:
                    return False

                if plate and plate.upper() not in str(vehicle.get("plate_number", "")).upper():
                    return False

                if vehicle_class and str(vehicle.get("vehicle_class", "")).lower() != vehicle_class.lower():
                    return False

                if status and str(item.get("violation_status", "")).lower() != status.lower():
                    return False

                ts = str(item.get("timestamp", ""))
                if from_ts and ts < from_ts:
                    return False
                if to_ts and ts > to_ts:
                    return False

                return True

            items = [item for item in items if matches(item)]

        return items[:limit]

    def by_id(self, violation_id: str) -> Optional[Dict[str, Any]]:
        for item in self.list_all(limit=10_000):
            if item.get("violation_id") == violation_id:
                return item
        return None

    def summary(self) -> Dict[str, Any]:
        items = self._load_all()
        if not items:
            return {
                "total_violations": 0,
                "unique_plates": 0,
                "avg_speed_kmph": 0.0,
                "avg_ocr_confidence": 0.0,
                "by_class": {},
                "by_hour": {},
            }

        plates = set()
        speed_values: List[float] = []
        conf_values: List[float] = []
        by_class: Dict[str, int] = {}
        by_hour: Dict[str, int] = {}

        for item in items:
            vehicle = item.get("vehicle", {})
            plate = vehicle.get("plate_number")
            if isinstance(plate, str) and plate:
                plates.add(plate)

            speed = vehicle.get("estimated_speed_kmph")
            if isinstance(speed, (float, int)):
                speed_values.append(float(speed))

            confidence = vehicle.get("plate_ocr_confidence")
            if isinstance(confidence, (float, int)):
                conf_values.append(float(confidence))

            klass = str(vehicle.get("vehicle_class", "unknown"))
            by_class[klass] = by_class.get(klass, 0) + 1

            hour_key = str(item.get("timestamp", ""))[:13]
            if hour_key:
                by_hour[hour_key] = by_hour.get(hour_key, 0) + 1

        avg_speed = sum(speed_values) / len(speed_values) if speed_values else 0.0
        avg_conf = sum(conf_values) / len(conf_values) if conf_values else 0.0

        return {
            "total_violations": len(items),
            "unique_plates": len(plates),
            "avg_speed_kmph": round(avg_speed, 2),
            "avg_ocr_confidence": round(avg_conf, 3),
            "by_class": by_class,
            "by_hour": by_hour,
        }
