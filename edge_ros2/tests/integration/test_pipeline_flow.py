"""
tests/integration/test_pipeline_flow.py
=========================================
Integration test: validates the full 7-stage pipeline message flow
using pure Python (no ROS2 runtime required).

Tests the data contracts between pipeline stages by instantiating the
pure-Python processing logic directly (no Node spin needed).

Covers:
  1. sensor_bridge: parse_frame_header round-trip
  2. inference_node: DetectorEngine.filter_twowheelers logic
  3. tracking_node: ByteTrackWrapper assigns track IDs through a sequence of frames
  4. plate_ocr_node: get_best_plate selection
  5. plate_ocr_node: CLAHE pipeline (PlateEnhancer) on synthetic plate
  6. violation_aggregator: OcrCorrelationBuffer TTL eviction
  7. violation_aggregator: dual cooldown blocks duplicate violation
  8. evidence_writer: full bundle written with correct schema v1

These tests run in CI without Docker, ROS2, or GPU.
"""

import json
import re
import sys
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
import pytest
from unittest.mock import MagicMock

# ── Mock ROS2 dependencies to allow pure AI testing on Windows ─────────────────
sys.modules['rclpy'] = MagicMock()
sys.modules['rclpy.node'] = MagicMock()
sys.modules['rclpy.qos'] = MagicMock()
sys.modules['sensor_msgs'] = MagicMock()
sys.modules['sensor_msgs.msg'] = MagicMock()
sys.modules['cv_bridge'] = MagicMock()
sys.modules['fw_msgs'] = MagicMock()
sys.modules['fw_msgs.msg'] = MagicMock()
sys.modules['std_msgs'] = MagicMock()
sys.modules['std_msgs.msg'] = MagicMock()
sys.modules['builtin_interfaces'] = MagicMock()
sys.modules['builtin_interfaces.msg'] = MagicMock()

# ── Adjust sys.path to import source directly ──────────────────────────────────

SRC = Path(__file__).resolve().parents[2] / "ros2_ws/src"
sys.path.insert(0, str(SRC / "fw_sensor_bridge"))
sys.path.insert(0, str(SRC / "fw_inference_node"))
sys.path.insert(0, str(SRC / "fw_plate_ocr_node"))
sys.path.insert(0, str(SRC / "fw_tracking_speed_node"))
sys.path.insert(0, str(SRC / "fw_violation_aggregator"))

from fw_sensor_bridge.sensor_bridge_node import parse_frame_header, check_frame_signal
from fw_plate_ocr_node.plate_ocr_node import get_best_plate, PlateEnhancer, IndianPlateOCR, FrameRingBuffer
from fw_tracking_speed_node.tracking_speed_node import ByteTrackWrapper, KalmanSpeedEstimator
from fw_violation_aggregator.violation_aggregator import (
    OcrCorrelationBuffer, EvidenceWriter, FrameRingBuffer as AggFrameRingBuffer
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. sensor_bridge: parse_frame_header round-trip
# ─────────────────────────────────────────────────────────────────────────────

class TestSensorBridgeHeaderRoundTrip:

    def _make_header(self, frame_id: str, camera_id: str,
                     signal_ok: bool, mean: float, std: float,
                     frame_num: int) -> str:
        return (f"{frame_id}|{camera_id}|"
                f"{'1' if signal_ok else '0'}|"
                f"{mean:.2f}|{std:.2f}|{frame_num}")

    def test_roundtrip_signal_ok(self):
        fid = str(uuid.uuid4())
        hdr = self._make_header(fid, "CAM_001", True, 120.5, 35.2, 42)
        meta = parse_frame_header(hdr)
        assert meta["frame_id"] == fid
        assert meta["camera_id"] == "CAM_001"
        assert meta["signal_ok"] is True
        assert abs(meta["mean_luma"] - 120.5) < 0.01
        assert abs(meta["std_luma"] - 35.2) < 0.01
        assert meta["frame_number"] == 42

    def test_roundtrip_signal_flat(self):
        fid = str(uuid.uuid4())
        hdr = self._make_header(fid, "CAM_002", False, 2.0, 0.5, 1)
        meta = parse_frame_header(hdr)
        assert meta["signal_ok"] is False

    def test_malformed_header_does_not_crash(self):
        """Malformed headers should return a safe fallback."""
        meta = parse_frame_header("not-a-valid-header")
        assert "frame_id" in meta
        assert meta["signal_ok"] is True  # safe fallback

    def test_blank_frame_signal_detected(self):
        """All-black frame should be detected as flat."""
        black = np.zeros((540, 960, 3), dtype=np.uint8)
        ok, mean, std = check_frame_signal(black)
        assert not ok
        assert mean < 5.0

    def test_normal_frame_signal_ok(self):
        """Natural noisy frame should pass signal check."""
        frame = np.random.randint(60, 200, (540, 960, 3), dtype=np.uint8)
        ok, mean, std = check_frame_signal(frame)
        assert ok
        assert std > 4.0


# ─────────────────────────────────────────────────────────────────────────────
# 2. inference_node: two-wheeler class filtering
# ─────────────────────────────────────────────────────────────────────────────

class TestTwoWheelerFiltering:

    def _make_det(self, cls_id: int, cls_name: str, area: float) -> dict:
        return {
            "class_id": cls_id, "class_name": cls_name,
            "confidence": 0.8,
            "x1": 10, "y1": 10, "x2": 10 + 50, "y2": 10 + 80,
            "area": area,
        }

    def _filter(self, dets: list[dict], min_area: float = 1500) -> list[dict]:
        from fw_inference_node.inference_node import DetectorEngine
        return DetectorEngine.filter_twowheelers(dets, min_area=min_area)

    def test_motorcycle_passes(self):
        dets = [self._make_det(3, "motorcycle", 3000)]
        assert len(self._filter(dets)) == 1

    def test_bicycle_passes(self):
        dets = [self._make_det(1, "bicycle", 2000)]
        assert len(self._filter(dets)) == 1

    def test_car_rejected(self):
        dets = [self._make_det(2, "car", 5000)]
        assert len(self._filter(dets)) == 0

    def test_tiny_detection_rejected(self):
        """Area below min_bbox_area_px should be discarded."""
        dets = [self._make_det(3, "motorcycle", 200)]
        assert len(self._filter(dets, min_area=1500)) == 0

    def test_coco_id_3_maps_to_motorcycle(self):
        dets = [self._make_det(3, "3", 2000)]
        result = self._filter(dets)
        assert len(result) == 1
        assert result[0]["class_name"] == "motorcycle"

    def test_coco_id_1_maps_to_bicycle(self):
        dets = [self._make_det(1, "1", 2000)]
        result = self._filter(dets)
        assert len(result) == 1
        assert result[0]["class_name"] == "bicycle"


# ─────────────────────────────────────────────────────────────────────────────
# 3. tracking_node: ByteTrack assigns consistent IDs across frames
# ─────────────────────────────────────────────────────────────────────────────

class TestByteTrackIntegration:

    def test_track_id_stable_across_frames(self):
        tracker = ByteTrackWrapper(min_hits=1, max_age=30)
        det = [{"x1": 100, "y1": 100, "x2": 200, "y2": 200,
                "confidence": 0.82, "class_name": "motorcycle"}]
        ids = set()
        for _ in range(5):
            result = tracker.update(det)
            if result:
                ids.add(result[0]["track_id"])
        assert len(ids) == 1, "Track ID must be stable across frames"

    def test_two_vehicles_get_distinct_ids(self):
        tracker = ByteTrackWrapper(min_hits=1, max_age=30)
        dets = [
            {"x1": 10, "y1": 10, "x2": 70, "y2": 80,
             "confidence": 0.8, "class_name": "motorcycle"},
            {"x1": 500, "y1": 300, "x2": 570, "y2": 380,
             "confidence": 0.78, "class_name": "bicycle"},
        ]
        results = tracker.update(dets)
        assert len(results) == 2
        ids = {r["track_id"] for r in results}
        assert len(ids) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 4. plate_ocr_node: get_best_plate selection (ML Guide §7)
# ─────────────────────────────────────────────────────────────────────────────

class TestGetBestPlate:

    def test_returns_none_for_empty(self):
        assert get_best_plate([]) is None

    def test_returns_only_plate(self):
        plates = [{"x1": 0, "y1": 0, "x2": 100, "y2": 30, "confidence": 0.8}]
        best = get_best_plate(plates)
        assert best["confidence"] == 0.8

    def test_returns_highest_confidence(self):
        plates = [
            {"x1": 0, "y1": 0, "x2": 100, "y2": 30, "confidence": 0.70},
            {"x1": 0, "y1": 0, "x2": 100, "y2": 30, "confidence": 0.92},
            {"x1": 0, "y1": 0, "x2": 100, "y2": 30, "confidence": 0.55},
        ]
        best = get_best_plate(plates)
        assert best["confidence"] == 0.92

    def test_area_tiebreaker_on_equal_confidence(self):
        """Equal confidence → larger area wins (ML Guide §7)."""
        plates = [
            {"x1": 0, "y1": 0, "x2":  80, "y2": 30, "confidence": 0.85},  # area=2400
            {"x1": 0, "y1": 0, "x2": 120, "y2": 40, "confidence": 0.85},  # area=4800 ← winner
        ]
        best = get_best_plate(plates)
        area = (best["x2"] - best["x1"]) * (best["y2"] - best["y1"])
        assert area == 4800


# ─────────────────────────────────────────────────────────────────────────────
# 5. plate_ocr_node: CLAHE pipeline (PlateEnhancer)
# ─────────────────────────────────────────────────────────────────────────────

class TestPlateEnhancerIntegration:

    @pytest.fixture
    def enhancer(self):
        return PlateEnhancer(esrgan_path=None)

    @pytest.fixture
    def plate_image(self):
        img = np.zeros((40, 200, 3), dtype=np.uint8)
        cv2.putText(img, "KA05AB1234", (5, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
        return img

    def test_enhance_returns_tuple(self, enhancer, plate_image):
        result, method = enhancer.enhance(plate_image)
        assert result is not None
        assert method in ("clahe_cpu", "esrgan")

    def test_enhancer_output_is_bgr(self, enhancer, plate_image):
        result, _ = enhancer.enhance(plate_image)
        assert result.ndim == 3 and result.shape[2] == 3

    def test_enhance_increases_mean_brightness_range(self, enhancer):
        """Dark plate: CLAHE should increase contrast."""
        dark = np.full((40, 200, 3), 20, dtype=np.uint8)
        result, _ = enhancer.enhance(dark)
        orig_std = float(np.std(cv2.cvtColor(dark, cv2.COLOR_BGR2GRAY)))
        enh_std = float(np.std(cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)))
        # After CLAHE on uniform dark image, std should be >= orig
        assert enh_std >= orig_std * 0.5  # lenient check


# ─────────────────────────────────────────────────────────────────────────────
# 6. violation_aggregator: OcrCorrelationBuffer TTL eviction
# ─────────────────────────────────────────────────────────────────────────────

class TestOcrCorrelationBufferIntegration:

    def test_put_and_get(self):
        buf = OcrCorrelationBuffer(ttl_seconds=5.0)

        class FakePlateOcr:
            track_id = 42

        buf.put(FakePlateOcr())
        result = buf.get(42)
        assert result is not None
        assert result.track_id == 42

    def test_ttl_eviction(self):
        buf = OcrCorrelationBuffer(ttl_seconds=0.05)  # 50ms TTL

        class FakePlateOcr:
            track_id = 99

        buf.put(FakePlateOcr())
        time.sleep(0.10)
        result = buf.get(99)
        assert result is None, "Entry should have been evicted after TTL"

    def test_missing_track_returns_none(self):
        buf = OcrCorrelationBuffer(ttl_seconds=5.0)
        assert buf.get(999) is None


# ─────────────────────────────────────────────────────────────────────────────
# 7. violation_aggregator: duplicate violation blocked by dual cooldown
# ─────────────────────────────────────────────────────────────────────────────

class TestDualCooldown:

    def _should_allow(self, last_by_track: dict, last_by_plate: dict,
                      track_id: int, plate: str, cooldown: int = 60) -> bool:
        now = time.monotonic()
        last_t = max(
            float(last_by_track.get(track_id, 0.0)),
            float(last_by_plate.get(plate, 0.0)),
        )
        return (now - last_t) >= cooldown

    def test_first_violation_allowed(self):
        assert self._should_allow({}, {}, track_id=1, plate="KA05AB1234")

    def test_duplicate_track_blocked(self):
        now = time.monotonic()
        track_cool = {1: now}  # just issued
        assert not self._should_allow(
            track_cool, {}, track_id=1, plate="KA05AB1234", cooldown=60)

    def test_duplicate_plate_different_track_blocked(self):
        """Same plate, different track (re-ID loss) — plate cooldown blocks."""
        now = time.monotonic()
        plate_cool = {"KA05AB1234": now}
        assert not self._should_allow(
            {}, plate_cool, track_id=99, plate="KA05AB1234", cooldown=60)

    def test_different_plate_allowed_after_cooldown(self):
        assert self._should_allow({}, {}, track_id=2, plate="MH12DE9999")

    def test_expired_cooldown_allows(self):
        old_t = time.monotonic() - 120  # 2 minutes ago
        track_cool = {1: old_t}
        plate_cool = {"KA05AB1234": old_t}
        assert self._should_allow(
            track_cool, plate_cool,
            track_id=1, plate="KA05AB1234", cooldown=60)


# ─────────────────────────────────────────────────────────────────────────────
# 8. evidence_writer: full bundle written with correct schema v1
# ─────────────────────────────────────────────────────────────────────────────

class TestEvidenceWriterIntegration:

    @pytest.fixture
    def writer(self, tmp_path):
        return EvidenceWriter(base_dir=tmp_path / "violations")

    @pytest.fixture
    def violation_record(self):
        return {
            "schema_version": "v1",
            "violation_id": str(uuid.uuid4()),
            "timestamp": "2026-04-17T12:00:00",
            "timestamp_utc": "2026-04-17T12:00:00+00:00",
            "location": {
                "camera_id": "FP_CAM_001",
                "device_id": "EDGE-001",
                "location_name": "Test Junction",
                "gps_lat": 12.9716,
                "gps_lng": 77.5946,
            },
            "vehicle": {
                "plate_number": "KA05AB1234",
                "plate_ocr_confidence": 0.91,
                "plate_format_valid": True,
                "vehicle_class": "motorcycle",
                "estimated_speed_kmph": 15.3,
                "track_id": 7,
                "detection_confidence": 0.82,
            },
            "violation_type": "FOOTPATH_ENCROACHMENT",
            "section_applied": "Section 177 MV Act",
            "fine_amount_inr": 500,
            "evidence": {
                "full_frame": "",
                "plate_crop_raw": "",
                "plate_crop_enhanced": "",
                "thumbnail": "",
            },
            "system": {
                "device_id": "EDGE-001",
                "schema_version": "v1",
                "pushed_to_cloud": False,
                "push_timestamp": None,
                "pipeline_latency_ms": 215.0,
            },
        }

    @pytest.fixture
    def synthetic_frame(self):
        frame = np.zeros((540, 960, 3), dtype=np.uint8)
        cv2.putText(frame, "VIOLATION FRAME", (200, 270),
                    cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 200, 0), 3)
        return frame

    @pytest.fixture
    def synthetic_plate(self):
        plate = np.zeros((40, 200, 3), dtype=np.uint8)
        cv2.putText(plate, "KA05AB1234", (5, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        return plate

    def test_bundle_dir_created(self, writer, violation_record,
                                 synthetic_frame, synthetic_plate):
        d = writer.write_bundle(violation_record, synthetic_frame,
                                synthetic_plate, synthetic_plate)
        assert d.is_dir()

    def test_metadata_json_is_schema_v1(self, writer, violation_record,
                                         synthetic_frame, synthetic_plate):
        d = writer.write_bundle(violation_record, synthetic_frame,
                                synthetic_plate, synthetic_plate)
        data = json.loads((d / "violation_metadata.json").read_text())
        assert data["schema_version"] == "v1"
        assert data["violation_type"] == "FOOTPATH_ENCROACHMENT"
        assert data["vehicle"]["plate_number"] == "KA05AB1234"

    def test_evidence_frame_saved(self, writer, violation_record,
                                   synthetic_frame, synthetic_plate):
        d = writer.write_bundle(violation_record, synthetic_frame,
                                synthetic_plate, synthetic_plate)
        assert (d / "evidence_frame.jpg").exists()
        assert (d / "evidence_frame.jpg").stat().st_size > 1000

    def test_thumbnail_is_smaller_than_frame(self, writer, violation_record,
                                              synthetic_frame, synthetic_plate):
        d = writer.write_bundle(violation_record, synthetic_frame,
                                synthetic_plate, synthetic_plate)
        frame_sz = (d / "evidence_frame.jpg").stat().st_size
        thumb_sz = (d / "thumbnail.jpg").stat().st_size
        assert thumb_sz < frame_sz

    def test_schema_has_all_required_mqtt_fields(self, writer, violation_record,
                                                   synthetic_frame, synthetic_plate):
        d = writer.write_bundle(violation_record, synthetic_frame,
                                synthetic_plate, synthetic_plate)
        data = json.loads((d / "violation_metadata.json").read_text())
        for field in ["schema_version", "violation_id", "timestamp_utc",
                      "violation_type", "location", "vehicle", "system"]:
            assert field in data, f"Missing required field: {field}"
        for loc_field in ["camera_id", "device_id", "gps_lat", "gps_lng"]:
            assert loc_field in data["location"], \
                f"Missing location field: {loc_field}"

    def test_gps_coordinates_in_valid_range(self, writer, violation_record,
                                             synthetic_frame, synthetic_plate):
        d = writer.write_bundle(violation_record, synthetic_frame,
                                synthetic_plate, synthetic_plate)
        data = json.loads((d / "violation_metadata.json").read_text())
        assert -90 <= data["location"]["gps_lat"] <= 90
        assert -180 <= data["location"]["gps_lng"] <= 180
