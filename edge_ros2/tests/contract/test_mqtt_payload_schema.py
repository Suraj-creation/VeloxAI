"""
Contract tests for the cloud bridge payloads.

These validate the strict backend-shaped JSON that the MQTT/HTTP bridge now
emits for telemetry and violations.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace


SRC = Path(__file__).resolve().parents[2] / "ros2_ws" / "src"
sys.path.insert(0, str(SRC / "fw_ros2_mqtt_bridge"))

from fw_ros2_mqtt_bridge.payloads import build_telemetry_payload, build_violation_payload


ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")


class FakeStamp:
    def __init__(self, sec: int, nanosec: int = 0) -> None:
        self.sec = sec
        self.nanosec = nanosec


def make_health_msg() -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=FakeStamp(1713859200),
        device_id="pi-001",
        camera_id="FP_CAM_001",
        pipeline_running=True,
        pipeline_fps=14.5,
        pipeline_latency_ms_p50=52.4,
        reconnects=1,
        frame_failures=0,
        camera_connected=True,
        camera_status="online",
        cpu_percent=44.1,
        memory_used_mb=512.0,
        cpu_temp_celsius=58.0,
        disk_free_gb=14.2,
        active_tracks=3,
        mqtt_offline_queue_depth=0,
    )


def make_violation_msg() -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=FakeStamp(1713859200),
        event_id="vio-123",
        device_id="pi-001",
        camera_id="FP_CAM_001",
        ts_utc="2026-04-23T10:15:00+00:00",
        event_type="FOOTPATH_ENCROACHMENT",
        track_id=77,
        class_name="motorcycle",
        speed_kmph=31.4,
        confidence=0.93,
        plate_text="KA05AB1234",
        ocr_confidence=0.88,
        plate_format_valid=True,
        gps_lat=12.9716,
        gps_lng=77.5946,
        location_name="Sample Junction",
        evidence_dir="violations/sample",
        evidence_uri="s3://bucket/violations/vio-123",
        total_pipeline_latency_ms=187.5,
    )


class TestTelemetryPayloadSchema:
    def test_required_fields_present(self) -> None:
        payload = build_telemetry_payload(make_health_msg())
        assert {
            "device_id",
            "camera_id",
            "timestamp",
            "fps",
            "latency_ms",
            "status",
        }.issubset(payload.keys())

    def test_timestamp_is_iso8601(self) -> None:
        payload = build_telemetry_payload(make_health_msg())
        assert ISO_RE.match(payload["timestamp"])

    def test_active_status_for_running_pipeline(self) -> None:
        payload = build_telemetry_payload(make_health_msg())
        assert payload["status"] == "active"


class TestViolationPayloadSchema:
    def test_required_fields_present(self) -> None:
        payload = build_violation_payload(make_violation_msg())
        assert {"violation_id", "timestamp", "location", "vehicle"}.issubset(payload.keys())

    def test_nested_location_matches_backend_contract(self) -> None:
        payload = build_violation_payload(make_violation_msg())
        assert payload["location"]["camera_id"] == "FP_CAM_001"
        assert payload["location"]["gps_lat"] == 12.9716
        assert payload["location"]["gps_lng"] == 77.5946

    def test_nested_vehicle_matches_backend_contract(self) -> None:
        payload = build_violation_payload(make_violation_msg())
        assert payload["vehicle"]["plate_number"] == "KA05AB1234"
        assert payload["vehicle"]["estimated_speed_kmph"] == 31.4
        assert payload["vehicle"]["track_id"] == 77

    def test_event_id_becomes_violation_id(self) -> None:
        payload = build_violation_payload(make_violation_msg())
        assert payload["violation_id"] == "vio-123"
