from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from services.common.config import load_settings


DEFAULT_LAB_CONFIG: Dict[str, Any] = {
    "cameraId": "FP_CAM_001",
    "locationName": "Sample Junction",
    "gpsLat": "12.9716",
    "gpsLng": "77.5946",
    "sourceMode": "device",
    "sourceValue": "0",
    "selectedDeviceId": "",
    "previewWidth": 1280,
    "previewHeight": 720,
    "targetFps": 15,
    "detectionConfidence": 0.35,
    "speedThresholdKmph": 5.0,
    "minOcrConfidence": 0.65,
    "cooldownSec": 60,
    "generalModel": "YOLOv8n General Objects",
    "enforcementModel": "YOLOv8n Two-Wheeler + LP + PaddleOCR",
    "enablePlatePipeline": True,
}


class EdgeRuntimeRepository:
    def __init__(self) -> None:
        settings = load_settings()
        self._backend_root: Path = settings.project_root
        self._edge_root: Path = settings.project_root.parent / "objective_3_footpath"
        self._config_dir: Path = self._edge_root / "config"
        self._metrics_path: Path = self._edge_root / ".metrics.json"
        self._preview_frame_path: Path = self._edge_root / ".preview_annotated.jpg"
        self._footpath_cfg_path: Path = self._config_dir / "footpath_roi.json"
        self._speed_cfg_path: Path = self._config_dir / "speed_calibration.json"
        self._dashboard_cfg_path: Path = self._config_dir / "dashboard.json"
        self._ingest_cfg_path: Path = self._config_dir / "backend_ingest.json"
        self._lab_cfg_path: Path = self._config_dir / "frontend_camera_lab.json"

    def _load_json(self, path: Path, fallback: Dict[str, Any]) -> Dict[str, Any]:
        if not path.exists():
            return fallback

        try:
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
            if isinstance(value, dict):
                return value
            return fallback
        except Exception:
            return fallback

    def _save_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        temp_path.replace(path)

    def _file_timestamp(self, path: Path) -> Optional[str]:
        if not path.exists():
            return None

        stat = path.stat()
        return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    def _file_age_seconds(self, path: Path) -> Optional[float]:
        if not path.exists():
            return None

        try:
            return max(0.0, time.time() - float(path.stat().st_mtime))
        except Exception:
            return None

    def _to_int(self, raw: Any, fallback: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(raw)
            return max(minimum, min(maximum, parsed))
        except Exception:
            return fallback

    def _to_float(self, raw: Any, fallback: float, minimum: float, maximum: float) -> float:
        try:
            parsed = float(raw)
            return max(minimum, min(maximum, parsed))
        except Exception:
            return fallback

    def _to_bool(self, raw: Any, fallback: bool) -> bool:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        return fallback

    def _resolve_config(self) -> Dict[str, Any]:
        footpath = self._load_json(self._footpath_cfg_path, {})
        speed = self._load_json(self._speed_cfg_path, {})
        dashboard = self._load_json(self._dashboard_cfg_path, {})
        ingest = self._load_json(self._ingest_cfg_path, {})
        lab = self._load_json(self._lab_cfg_path, {})

        resolved = {
            **DEFAULT_LAB_CONFIG,
            **lab,
        }

        resolved["cameraId"] = str(lab.get("cameraId") or footpath.get("camera_id") or DEFAULT_LAB_CONFIG["cameraId"])
        resolved["locationName"] = str(lab.get("locationName") or footpath.get("location_name") or DEFAULT_LAB_CONFIG["locationName"])
        resolved["gpsLat"] = str(lab.get("gpsLat") or footpath.get("gps_lat") or DEFAULT_LAB_CONFIG["gpsLat"])
        resolved["gpsLng"] = str(lab.get("gpsLng") or footpath.get("gps_lng") or DEFAULT_LAB_CONFIG["gpsLng"])
        resolved["targetFps"] = self._to_int(lab.get("targetFps", speed.get("camera_fps")), 15, 1, 60)
        resolved["pixelsPerMetre"] = self._to_float(speed.get("pixels_per_metre"), 47.0, 1.0, 500.0)
        resolved["detectionConfidence"] = self._to_float(resolved.get("detectionConfidence"), 0.35, 0.1, 0.95)
        resolved["speedThresholdKmph"] = self._to_float(resolved.get("speedThresholdKmph"), 5.0, 1.0, 50.0)
        resolved["minOcrConfidence"] = self._to_float(resolved.get("minOcrConfidence"), 0.65, 0.3, 0.99)
        resolved["cooldownSec"] = self._to_int(resolved.get("cooldownSec"), 60, 5, 600)
        resolved["previewWidth"] = self._to_int(resolved.get("previewWidth"), 1280, 320, 3840)
        resolved["previewHeight"] = self._to_int(resolved.get("previewHeight"), 720, 240, 2160)
        resolved["enablePlatePipeline"] = self._to_bool(resolved.get("enablePlatePipeline"), True)
        resolved["sourceMode"] = "rtsp" if str(resolved.get("sourceMode", "device")) == "rtsp" else "device"
        resolved["sourceValue"] = str(resolved.get("sourceValue", "0"))
        resolved["selectedDeviceId"] = str(resolved.get("selectedDeviceId", ""))
        resolved["generalModel"] = str(resolved.get("generalModel", DEFAULT_LAB_CONFIG["generalModel"]))
        resolved["enforcementModel"] = str(resolved.get("enforcementModel", DEFAULT_LAB_CONFIG["enforcementModel"]))

        return {
            "resolved": resolved,
            "files": {
                "footpath": footpath,
                "speed_calibration": speed,
                "dashboard": dashboard,
                "ingest": ingest,
                "frontend_camera_lab": lab,
            },
        }

    def get_runtime_status(self) -> Dict[str, Any]:
        metrics = self._load_json(self._metrics_path, {})
        metrics_age_sec = self._file_age_seconds(self._metrics_path)
        preview_age_sec = self._file_age_seconds(self._preview_frame_path)

        freshness_window_sec = 6.0
        metrics_fresh = metrics_age_sec is not None and metrics_age_sec <= freshness_window_sec
        preview_fresh = preview_age_sec is not None and preview_age_sec <= freshness_window_sec

        running = bool(metrics.get("running", False)) and metrics_fresh
        has_preview = self._preview_frame_path.exists() and preview_fresh

        return {
            "edge_root": str(self._edge_root),
            "edge_root_exists": self._edge_root.exists(),
            "runtime": {
                "running": running,
                "has_preview_frame": has_preview,
                "preview_updated_at": self._file_timestamp(self._preview_frame_path),
                "metrics_updated_at": self._file_timestamp(self._metrics_path),
                "preview_age_sec": round(preview_age_sec, 2) if preview_age_sec is not None else None,
                "metrics_age_sec": round(metrics_age_sec, 2) if metrics_age_sec is not None else None,
                "freshness_window_sec": freshness_window_sec,
            },
            "metrics": metrics,
        }

    def get_preview_frame_bytes(self) -> Optional[bytes]:
        if not self._preview_frame_path.exists():
            return None

        try:
            return self._preview_frame_path.read_bytes()
        except Exception:
            return None

    def get_config(self) -> Dict[str, Any]:
        payload = self._resolve_config()
        payload["edge_root"] = str(self._edge_root)
        payload["edge_root_exists"] = self._edge_root.exists()
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    def update_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        current = self._resolve_config()
        merged = {
            **current["resolved"],
            **(payload if isinstance(payload, dict) else {}),
        }

        normalized = {
            **DEFAULT_LAB_CONFIG,
            **merged,
        }

        normalized["cameraId"] = str(normalized.get("cameraId") or DEFAULT_LAB_CONFIG["cameraId"])
        normalized["locationName"] = str(normalized.get("locationName") or DEFAULT_LAB_CONFIG["locationName"])
        normalized["gpsLat"] = str(normalized.get("gpsLat") or DEFAULT_LAB_CONFIG["gpsLat"])
        normalized["gpsLng"] = str(normalized.get("gpsLng") or DEFAULT_LAB_CONFIG["gpsLng"])
        normalized["sourceMode"] = "rtsp" if str(normalized.get("sourceMode")) == "rtsp" else "device"
        normalized["sourceValue"] = str(normalized.get("sourceValue") or "0")
        normalized["selectedDeviceId"] = str(normalized.get("selectedDeviceId") or "")
        normalized["previewWidth"] = self._to_int(normalized.get("previewWidth"), 1280, 320, 3840)
        normalized["previewHeight"] = self._to_int(normalized.get("previewHeight"), 720, 240, 2160)
        normalized["targetFps"] = self._to_int(normalized.get("targetFps"), 15, 1, 60)
        normalized["detectionConfidence"] = self._to_float(normalized.get("detectionConfidence"), 0.35, 0.1, 0.95)
        normalized["speedThresholdKmph"] = self._to_float(normalized.get("speedThresholdKmph"), 5.0, 1.0, 50.0)
        normalized["minOcrConfidence"] = self._to_float(normalized.get("minOcrConfidence"), 0.65, 0.3, 0.99)
        normalized["cooldownSec"] = self._to_int(normalized.get("cooldownSec"), 60, 5, 600)
        normalized["generalModel"] = str(normalized.get("generalModel") or DEFAULT_LAB_CONFIG["generalModel"])
        normalized["enforcementModel"] = str(normalized.get("enforcementModel") or DEFAULT_LAB_CONFIG["enforcementModel"])
        normalized["enablePlatePipeline"] = self._to_bool(normalized.get("enablePlatePipeline"), True)

        normalized["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._save_json(self._lab_cfg_path, normalized)

        footpath = self._load_json(self._footpath_cfg_path, {})
        footpath["camera_id"] = normalized["cameraId"]
        footpath["location_name"] = normalized["locationName"]
        try:
            footpath["gps_lat"] = float(normalized["gpsLat"])
        except Exception:
            footpath["gps_lat"] = footpath.get("gps_lat", 0.0)
        try:
            footpath["gps_lng"] = float(normalized["gpsLng"])
        except Exception:
            footpath["gps_lng"] = footpath.get("gps_lng", 0.0)
        self._save_json(self._footpath_cfg_path, footpath)

        speed = self._load_json(self._speed_cfg_path, {})
        speed["camera_fps"] = normalized["targetFps"]
        if "pixelsPerMetre" in payload:
            speed["pixels_per_metre"] = self._to_float(payload.get("pixelsPerMetre"), 47.0, 1.0, 500.0)
        self._save_json(self._speed_cfg_path, speed)

        return self.get_config()
