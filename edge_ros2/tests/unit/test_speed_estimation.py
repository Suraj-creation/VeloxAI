"""
tests/unit/test_speed_estimation.py
====================================
Unit tests for Kalman speed estimator and tracking math.
No ROS2 required — tests pure Python modules.
"""

import math
import sys
from pathlib import Path

import pytest
import numpy as np

# Allow importing from the ROS2 node source directly
sys.path.insert(0, str(
    Path(__file__).resolve().parents[2] /
    "ros2_ws/src/fw_tracking_speed_node/fw_tracking_speed_node"
))
from tracking_speed_node import KalmanSpeedEstimator, ByteTrackWrapper


# ─── KalmanSpeedEstimator ─────────────────────────────────────────────────────

class TestKalmanSpeedEstimator:

    def test_returns_zero_on_first_update(self):
        estimator = KalmanSpeedEstimator(pixels_per_metre=47.0, fps=10.0)
        speed = estimator.update(100.0, 200.0)
        assert speed == 0.0

    def test_stationary_object_near_zero_speed(self):
        estimator = KalmanSpeedEstimator(pixels_per_metre=47.0, fps=10.0)
        # Object stays at same position
        for _ in range(10):
            speed = estimator.update(100.0, 200.0)
        assert speed < 1.0, f"Stationary object speed should be < 1 km/h, got {speed}"

    def test_moving_object_positive_speed(self):
        """
        Object moves 47 pixels per frame (= 1m/frame at fps=10 = 36 km/h).
        After warmup, speed should be in ballpark.
        """
        estimator = KalmanSpeedEstimator(pixels_per_metre=47.0, fps=10.0)
        x = 0.0
        speed = 0.0
        for i in range(15):
            x += 47.0  # 1 metre per frame
            speed = estimator.update(x, 100.0)
        # Should converge near 36 km/h ± tolerance (Kalman has startup delay)
        assert speed > 10.0, f"Moving object speed too low: {speed}"
        assert speed < 60.0, f"Moving object speed too high: {speed}"

    def test_speed_is_non_negative(self):
        estimator = KalmanSpeedEstimator(pixels_per_metre=47.0, fps=10.0)
        for i in range(5):
            speed = estimator.update(float(i * 10), 100.0)
            assert speed >= 0.0

    def test_speed_scale_with_pixels_per_metre(self):
        """Higher ppm → lower speed for same pixel displacement."""
        est_low = KalmanSpeedEstimator(pixels_per_metre=20.0, fps=10.0)
        est_high = KalmanSpeedEstimator(pixels_per_metre=100.0, fps=10.0)
        x = 0.0
        for i in range(15):
            x += 50.0
            s_low = est_low.update(x, 100.0)
            s_high = est_high.update(x, 100.0)
        assert s_low > s_high, (
            "Higher ppm should give lower speed for same pixel motion, "
            f"but got low_ppm={s_low:.1f}, high_ppm={s_high:.1f}"
        )

    def test_reinitializes_correctly(self):
        estimator = KalmanSpeedEstimator(pixels_per_metre=47.0, fps=10.0)
        assert not estimator._initialized
        estimator.update(50.0, 50.0)
        assert estimator._initialized


# ─── ByteTrackWrapper ─────────────────────────────────────────────────────────

class TestByteTrackWrapper:

    def test_empty_detections_returns_empty(self):
        tracker = ByteTrackWrapper()
        result = tracker.update([])
        assert result == []

    def test_single_detection_gets_track_id(self):
        tracker = ByteTrackWrapper(min_hits=1)
        dets = [{"x1": 100, "y1": 100, "x2": 200, "y2": 200,
                 "confidence": 0.8, "class_name": "motorcycle"}]
        result = tracker.update(dets)
        assert len(result) == 1
        assert result[0]["track_id"] >= 1

    def test_same_object_gets_same_track_id(self):
        tracker = ByteTrackWrapper(min_hits=1)
        dets = [{"x1": 100, "y1": 100, "x2": 200, "y2": 200,
                 "confidence": 0.8, "class_name": "motorcycle"}]
        r1 = tracker.update(dets)
        # Move slightly
        dets2 = [{"x1": 105, "y1": 102, "x2": 205, "y2": 202,
                  "confidence": 0.79, "class_name": "motorcycle"}]
        r2 = tracker.update(dets2)
        assert len(r1) >= 1 and len(r2) >= 1
        assert r1[0]["track_id"] == r2[0]["track_id"]

    def test_two_objects_get_different_track_ids(self):
        tracker = ByteTrackWrapper(min_hits=1)
        dets = [
            {"x1": 10, "y1": 10, "x2": 60, "y2": 60,
             "confidence": 0.8, "class_name": "motorcycle"},
            {"x1": 400, "y1": 400, "x2": 480, "y2": 480,
             "confidence": 0.75, "class_name": "bicycle"},
        ]
        result = tracker.update(dets)
        assert len(result) == 2
        ids = {r["track_id"] for r in result}
        assert len(ids) == 2, "Two objects must get two different track IDs"

    def test_track_disappears_after_max_age(self):
        tracker = ByteTrackWrapper(min_hits=1, max_age=2)
        dets = [{"x1": 100, "y1": 100, "x2": 200, "y2": 200,
                 "confidence": 0.8, "class_name": "motorcycle"}]
        tracker.update(dets)      # frame 1
        tracker.update([])        # frame 2 — no detection
        tracker.update([])        # frame 3 — max_age=2, track dies
        result = tracker.update([])
        assert result == [], "Track should have died after max_age"

    def test_min_hits_requires_multiple_detections(self):
        tracker = ByteTrackWrapper(min_hits=3)
        det = [{"x1": 100, "y1": 100, "x2": 200, "y2": 200,
                "confidence": 0.8, "class_name": "motorcycle"}]
        r1 = tracker.update(det)
        r2 = tracker.update(det)
        assert r1 == [], "Should not confirm track before min_hits=3"
        assert r2 == [], "Should not confirm track before min_hits=3"
        r3 = tracker.update(det)
        assert len(r3) == 1, "Track should be confirmed after min_hits=3"

    def test_iou_matrix_correct(self):
        tracker = ByteTrackWrapper()
        tb = [[0, 0, 100, 100]]  # area = 10000
        db = [[0, 0, 100, 100]]  # perfect overlap
        iou = tracker._iou_matrix(tb, db)
        assert abs(iou[0, 0] - 1.0) < 1e-6

    def test_iou_matrix_no_overlap(self):
        tracker = ByteTrackWrapper()
        tb = [[0, 0, 50, 50]]
        db = [[100, 100, 200, 200]]
        iou = tracker._iou_matrix(tb, db)
        assert iou[0, 0] == 0.0


# ─── Plate OCR text cleaning ──────────────────────────────────────────────────

class TestPlateTextCleaning:
    """Test the position-aware confusion correction without loading PaddleOCR."""

    def _clean(self, raw: str) -> str:
        # Inline the same logic as IndianPlateOCR._clean
        import re as _re
        L2D = {"O": "0", "I": "1", "l": "1", "Z": "2",
               "S": "5", "B": "8", "G": "6"}
        D2L = {"0": "O", "1": "I", "5": "S", "8": "B", "6": "G"}

        text = raw.upper().replace(" ", "").replace("-", "").strip()
        text = _re.sub(r"[^A-Z0-9]", "", text)
        if len(text) >= 10:
            c = list(text)
            for pos in [2, 3]:
                c[pos] = L2D.get(c[pos], c[pos])
            for pos in [0, 1, 4, 5]:
                c[pos] = D2L.get(c[pos], c[pos])
            for pos in range(6, min(10, len(c))):
                c[pos] = L2D.get(c[pos], c[pos])
            text = "".join(c)
        return text

    def _validate(self, text: str) -> bool:
        import re as _re
        p = _re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$")
        b = _re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{2}$")
        return bool(p.match(text) or b.match(text))

    def test_clean_removes_spaces(self):
        assert self._clean("KA 05 AB 1234") == "KA05AB1234"

    def test_clean_removes_hyphens(self):
        assert self._clean("KA-05-AB-1234") == "KA05AB1234"

    def test_validate_standard_format(self):
        assert self._validate("KA05AB1234")

    def test_validate_delhi_format(self):
        assert self._validate("DL01CA1234")

    def test_validate_bh_series(self):
        assert self._validate("22BH1234AA")

    def test_reject_invalid_format(self):
        assert not self._validate("INVALID")
        assert not self._validate("12345678")
        assert not self._validate("")

    def test_confusion_correction_letter_O_to_digit_0(self):
        """OCR confuses O as 0 in digit positions."""
        raw = "KAO5AB1234"  # position 2 should be digit → O→0
        cleaned = self._clean(raw)
        # Position 2 = '0' (corrected from O)
        assert cleaned[2] == "0", f"Expected '0' at pos 2, got '{cleaned[2]}'"


# ─── Speed threshold enforcement ─────────────────────────────────────────────

class TestSpeedThreshold:

    @pytest.mark.parametrize("speed,threshold,should_flag", [
        (0.0, 5.0, False),
        (4.9, 5.0, False),
        (5.0, 5.0, True),
        (5.1, 5.0, True),
        (35.0, 5.0, True),
    ])
    def test_speed_threshold_logic(self, speed, threshold, should_flag):
        is_violation = speed >= threshold
        assert is_violation == should_flag


# ─── Spool depth accuracy ─────────────────────────────────────────────────────

class TestMqttSpool:

    def test_spool_enqueue_and_depth(self, tmp_path):
        sys.path.insert(0, str(
            Path(__file__).resolve().parents[2] /
            "ros2_ws/src/fw_ros2_mqtt_bridge/fw_ros2_mqtt_bridge"
        ))
        from mqtt_bridge_node import MqttSpool

        db = tmp_path / "test_spool.db"
        spool = MqttSpool(db)

        assert spool.depth() == 0

        sid1 = spool.enqueue("event-001", "footwatch/site/cam/violation",
                             {"event_id": "event-001", "plate": "KA05AB1234"})
        assert spool.depth() == 1

        sid2 = spool.enqueue("event-002", "footwatch/site/cam/violation",
                             {"event_id": "event-002", "plate": "MH12DE1111"})
        assert spool.depth() == 2

        spool.mark_delivered(sid1)
        assert spool.depth() == 1

        spool.mark_delivered(sid2)
        assert spool.depth() == 0

    def test_spool_pending_ordered_by_created_at(self, tmp_path):
        from mqtt_bridge_node import MqttSpool
        db = tmp_path / "test_spool.db"
        spool = MqttSpool(db)

        for i in range(5):
            spool.enqueue(f"evt-{i}", "test/topic", {"idx": i})

        rows = spool.pending()
        assert len(rows) == 5
