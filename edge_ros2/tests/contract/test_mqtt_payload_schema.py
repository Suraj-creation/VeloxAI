"""
tests/contract/test_mqtt_payload_schema.py
==========================================
Contract tests: Verify MQTT payload structures match schema v1.
These run without ROS2 or any ML models — pure Python.

Tests:
  - Violation payload has all required fields
  - Health payload has all required fields
  - event_id is a valid UUID (idempotency key)
  - schema_version is "v1"
  - GPS coordinates are floats within valid ranges
  - speed_kmph is a non-negative float
  - ocr_confidence is 0.0–1.0
"""

import json
import re
import uuid
import pytest
from pathlib import Path

# ─── Schema definitions ───────────────────────────────────────────────────────

VIOLATION_REQUIRED_FIELDS = {
    "schema_version", "event_id", "device_id", "camera_id",
    "ts_utc", "event_type", "speed_kmph", "class_name",
    "confidence", "plate_text", "ocr_confidence",
    "gps_lat", "gps_lng", "location_name", "pipeline_latency_ms",
}

HEALTH_REQUIRED_FIELDS = {
    "schema_version", "device_id", "camera_id", "ts_utc",
    "pipeline_running", "pipeline_fps", "cpu_percent",
    "memory_used_mb", "cpu_temp_c", "disk_free_gb",
    "camera_connected", "camera_status",
}

UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)

# ─── Fixture: sample violation payload ────────────────────────────────────────

@pytest.fixture
def sample_violation_payload():
    return {
        "schema_version": "v1",
        "event_id": str(uuid.uuid4()),
        "device_id": "EDGE-001",
        "camera_id": "FP_CAM_001",
        "ts_utc": "2026-04-17T07:00:00+00:00",
        "event_type": "FOOTPATH_ENCROACHMENT",
        "speed_kmph": 12.5,
        "class_name": "motorcycle",
        "confidence": 0.82,
        "plate_text": "KA05AB1234",
        "ocr_confidence": 0.91,
        "gps_lat": 12.9716,
        "gps_lng": 77.5946,
        "location_name": "Sample Junction",
        "evidence_uri": "",
        "pipeline_latency_ms": 215.3,
    }


@pytest.fixture
def sample_health_payload():
    return {
        "schema_version": "v1",
        "device_id": "EDGE-001",
        "camera_id": "FP_CAM_001",
        "ts_utc": "2026-04-17T07:00:00+00:00",
        "pipeline_running": True,
        "pipeline_fps": 9.8,
        "pipeline_latency_ms_p50": 88.0,
        "active_tracks": 2,
        "violations_session": 3,
        "mqtt_spool_depth": 0,
        "cpu_percent": 45.2,
        "memory_used_mb": 1850.0,
        "cpu_temp_c": 62.3,
        "disk_free_gb": 24.1,
        "camera_connected": True,
        "camera_status": "online",
        "frame_failures": 0,
        "reconnects": 0,
    }


# ─── Violation payload contract tests ─────────────────────────────────────────

class TestViolationPayloadSchema:

    def test_all_required_fields_present(self, sample_violation_payload):
        missing = VIOLATION_REQUIRED_FIELDS - sample_violation_payload.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_schema_version(self, sample_violation_payload):
        assert sample_violation_payload["schema_version"] == "v1"

    def test_event_id_is_valid_uuid(self, sample_violation_payload):
        eid = sample_violation_payload["event_id"]
        assert UUID_RE.match(eid), f"event_id is not a valid UUID v4: {eid}"

    def test_event_type_value(self, sample_violation_payload):
        assert sample_violation_payload["event_type"] == "FOOTPATH_ENCROACHMENT"

    def test_speed_non_negative(self, sample_violation_payload):
        assert sample_violation_payload["speed_kmph"] >= 0.0

    def test_speed_above_threshold(self, sample_violation_payload):
        """Confirmed violations must have speed > 5 km/h."""
        assert sample_violation_payload["speed_kmph"] >= 5.0

    def test_confidence_range(self, sample_violation_payload):
        conf = sample_violation_payload["confidence"]
        assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of [0,1]"

    def test_ocr_confidence_range(self, sample_violation_payload):
        oc = sample_violation_payload["ocr_confidence"]
        assert 0.0 <= oc <= 1.0, f"OCR confidence {oc} out of [0,1]"

    def test_gps_lat_range(self, sample_violation_payload):
        lat = sample_violation_payload["gps_lat"]
        assert -90.0 <= lat <= 90.0, f"gps_lat {lat} out of range"

    def test_gps_lng_range(self, sample_violation_payload):
        lng = sample_violation_payload["gps_lng"]
        assert -180.0 <= lng <= 180.0, f"gps_lng {lng} out of range"

    def test_plate_text_not_empty(self, sample_violation_payload):
        assert len(sample_violation_payload["plate_text"]) >= 8

    def test_plate_text_indian_format(self, sample_violation_payload):
        plate = sample_violation_payload["plate_text"]
        pattern = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$")
        bh_pattern = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{2}$")
        assert pattern.match(plate) or bh_pattern.match(plate), \
            f"Plate '{plate}' does not match Indian LP format"

    def test_pipeline_latency_positive(self, sample_violation_payload):
        assert sample_violation_payload["pipeline_latency_ms"] > 0

    def test_json_serializable(self, sample_violation_payload):
        """Ensure payload can be JSON-serialized (no datetime objects etc.)."""
        serialized = json.dumps(sample_violation_payload)
        reloaded = json.loads(serialized)
        assert reloaded["event_id"] == sample_violation_payload["event_id"]

    def test_unique_event_ids(self):
        """Two violation events must have different event_ids."""
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        assert id1 != id2


# ─── Health payload contract tests ────────────────────────────────────────────

class TestHealthPayloadSchema:

    def test_all_required_fields_present(self, sample_health_payload):
        missing = HEALTH_REQUIRED_FIELDS - sample_health_payload.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_schema_version(self, sample_health_payload):
        assert sample_health_payload["schema_version"] == "v1"

    def test_pipeline_running_is_bool(self, sample_health_payload):
        assert isinstance(sample_health_payload["pipeline_running"], bool)

    def test_cpu_percent_range(self, sample_health_payload):
        cpu = sample_health_payload["cpu_percent"]
        assert 0.0 <= cpu <= 100.0, f"cpu_percent {cpu} out of range"

    def test_camera_status_valid_values(self, sample_health_payload):
        valid = {"online", "signal_flat", "disconnected", "waiting", "waiting_frame"}
        status = sample_health_payload["camera_status"]
        assert status in valid, f"camera_status '{status}' not in {valid}"

    def test_fps_non_negative(self, sample_health_payload):
        assert sample_health_payload["pipeline_fps"] >= 0.0

    def test_json_serializable(self, sample_health_payload):
        serialized = json.dumps(sample_health_payload)
        reloaded = json.loads(serialized)
        assert reloaded["device_id"] == sample_health_payload["device_id"]
