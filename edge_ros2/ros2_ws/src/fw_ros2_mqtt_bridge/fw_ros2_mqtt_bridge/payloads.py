from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _read_value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _read_str(source: Any, key: str, default: str = "") -> str:
    value = _read_value(source, key, default)
    if value is None:
        return default
    return str(value)


def _read_float(source: Any, key: str, default: float = 0.0) -> float:
    value = _read_value(source, key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _read_int(source: Any, key: str, default: int = 0) -> int:
    value = _read_value(source, key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _read_bool(source: Any, key: str, default: bool = False) -> bool:
    value = _read_value(source, key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "active"}
    return bool(value)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ros_time_to_iso(stamp: Any, fallback: str | None = None) -> str:
    if stamp is None:
        return fallback or now_utc_iso()

    sec = _read_value(stamp, "sec", None)
    nanosec = _read_value(stamp, "nanosec", 0)
    if sec is None:
        return fallback or now_utc_iso()

    try:
        dt = datetime.fromtimestamp(
            float(sec) + (float(nanosec) / 1_000_000_000.0),
            tz=timezone.utc,
        )
    except (TypeError, ValueError, OSError):
        return fallback or now_utc_iso()
    return dt.isoformat()


def ensure_iso8601(value: str | None, fallback: str | None = None) -> str:
    text = (value or "").strip()
    if not text:
        return fallback or now_utc_iso()
    return text


def resolve_runtime_config(config_dir: Path, raw_cfg: Mapping[str, Any]) -> dict[str, Any]:
    cfg = dict(raw_cfg)

    cert_dir_value = str(cfg.get("cert_dir", "../certs")).strip() or "../certs"
    cert_dir_path = Path(cert_dir_value)
    if not cert_dir_path.is_absolute():
        cert_dir_path = (config_dir / cert_dir_path).resolve()

    http_api_key_env = str(cfg.get("http_api_key_env", "FW_INGEST_API_KEY")).strip()
    http_base_env = str(cfg.get("http_ingest_base_url_env", "FW_INGEST_API_BASE_URL")).strip()

    http_ingest_base_url = (
        os.getenv(http_base_env)
        or cfg.get("http_ingest_base_url")
        or cfg.get("backend_api_base_url")
        or ""
    )
    http_ingest_api_key = (
        os.getenv(http_api_key_env)
        or cfg.get("http_ingest_api_key")
        or cfg.get("backend_api_key")
        or ""
    )

    resolved = {
        **cfg,
        "cert_dir": str(cert_dir_path),
        "ca_cert": str(cfg.get("ca_cert", "rootCA.pem")),
        "device_cert": str(cfg.get("device_cert", "cert.pem")),
        "private_key": str(cfg.get("private_key", "private.key")),
        "keep_alive": int(cfg.get("keep_alive", 60)),
        "mqtt_enabled": bool(cfg.get("mqtt_enabled", True)),
        "http_enabled": bool(cfg.get("http_enabled", True)),
        "http_timeout_sec": float(cfg.get("http_timeout_sec", 10.0)),
        "http_ingest_base_url": str(http_ingest_base_url).rstrip("/"),
        "http_ingest_api_key": str(http_ingest_api_key),
        "http_api_key_env": http_api_key_env,
        "http_ingest_base_url_env": http_base_env,
        "mqtt_topic_prefix": str(cfg.get("mqtt_topic_prefix", "footwatch")).strip("/") or "footwatch",
        "mqtt_violation_topic": str(cfg.get("mqtt_violation_topic", "violations")).strip("/") or "violations",
        "mqtt_telemetry_topic": str(cfg.get("mqtt_telemetry_topic", "telemetry")).strip("/") or "telemetry",
        "mqtt_live_topic": str(cfg.get("mqtt_live_topic", "live")).strip("/") or "live",
    }
    return resolved


def build_telemetry_payload(msg: Any) -> dict[str, Any]:
    timestamp = ros_time_to_iso(_read_value(msg, "timestamp"))
    pipeline_running = _read_bool(msg, "pipeline_running", False)
    camera_connected = _read_bool(msg, "camera_connected", pipeline_running)
    camera_status = _read_str(msg, "camera_status", "waiting")

    if pipeline_running and camera_connected:
        status = "active"
    elif camera_connected:
        status = camera_status or "degraded"
    else:
        status = "offline"

    return {
        "device_id": _read_str(msg, "device_id", "pi-001"),
        "camera_id": _read_str(msg, "camera_id", "camera-001"),
        "timestamp": timestamp,
        "fps": _read_float(msg, "pipeline_fps"),
        "latency_ms": _read_float(msg, "pipeline_latency_ms_p50"),
        "status": status,
        "reconnects": _read_int(msg, "reconnects"),
        "frame_failures": _read_int(msg, "frame_failures"),
        "camera_connected": camera_connected,
        "camera_status": camera_status,
        "cpu_percent": _read_float(msg, "cpu_percent"),
        "memory_used_mb": _read_float(msg, "memory_used_mb"),
        "cpu_temp_c": _read_float(msg, "cpu_temp_celsius"),
        "disk_free_gb": _read_float(msg, "disk_free_gb"),
        "active_tracks": _read_int(msg, "active_tracks"),
        "mqtt_spool_depth": _read_int(msg, "mqtt_offline_queue_depth"),
        "location_name": _read_str(msg, "location_name", ""),
    }


def build_violation_payload(msg: Any) -> dict[str, Any]:
    violation_id = (
        _read_str(msg, "violation_id")
        or _read_str(msg, "event_id")
        or str(uuid.uuid4())
    )
    timestamp = ensure_iso8601(
        _read_str(msg, "ts_utc"),
        fallback=ros_time_to_iso(_read_value(msg, "timestamp")),
    )

    return {
        "violation_id": violation_id,
        "timestamp": timestamp,
        "location": {
            "camera_id": _read_str(msg, "camera_id", "camera-001"),
            "location_name": _read_str(msg, "location_name", ""),
            "gps_lat": _read_float(msg, "gps_lat"),
            "gps_lng": _read_float(msg, "gps_lng"),
        },
        "vehicle": {
            "plate_number": _read_str(msg, "plate_text", ""),
            "plate_ocr_confidence": _read_float(msg, "ocr_confidence"),
            "plate_format_valid": _read_bool(msg, "plate_format_valid", True),
            "vehicle_class": _read_str(msg, "class_name", "unknown"),
            "estimated_speed_kmph": _read_float(msg, "speed_kmph"),
            "track_id": _read_int(msg, "track_id"),
        },
        "device_id": _read_str(msg, "device_id", "pi-001"),
        "evidence": {
            "evidence_dir": _read_str(msg, "evidence_dir", ""),
            "evidence_uri": _read_str(msg, "evidence_uri", ""),
        },
        "confidence": _read_float(msg, "confidence"),
        "event_type": _read_str(msg, "event_type", "FOOTPATH_ENCROACHMENT"),
        "pipeline_latency_ms": _read_float(msg, "total_pipeline_latency_ms"),
    }


def build_live_payload(msg: Any) -> dict[str, Any]:
    timestamp = ros_time_to_iso(_read_value(msg, "timestamp"))
    return {
        "event_id": _read_str(msg, "event_id", str(uuid.uuid4())),
        "camera_id": _read_str(msg, "camera_id", "camera-001"),
        "timestamp": timestamp,
        "track_id": _read_int(msg, "track_id"),
        "class_name": _read_str(msg, "class_name", "unknown"),
        "plate_text": _read_str(msg, "plate_text", ""),
        "speed_kmph": _read_float(msg, "speed_kmph"),
        "ocr_confidence": _read_float(msg, "ocr_confidence"),
        "location": {
            "location_name": _read_str(msg, "location_name", ""),
            "gps_lat": _read_float(msg, "gps_lat"),
            "gps_lng": _read_float(msg, "gps_lng"),
        },
    }
