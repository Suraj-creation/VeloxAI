"""
tests/unit/test_evidence_writer.py
====================================
Unit tests for EvidenceWriter — violation bundle creation.
Uses tmp_path — no ROS2, no models.
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(
    Path(__file__).resolve().parents[2] /
    "ros2_ws/src/fw_violation_aggregator/fw_violation_aggregator"
))
from violation_aggregator import EvidenceWriter


@pytest.fixture
def writer(tmp_path):
    return EvidenceWriter(base_dir=tmp_path / "violations")


@pytest.fixture
def sample_record():
    return {
        "schema_version": "v1",
        "violation_id": "test-viol-001",
        "timestamp": "2026-04-17T07:00:00",
        "timestamp_utc": "2026-04-17T07:00:00+00:00",
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
            "track_id": 42,
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
            "pipeline_latency_ms": None,
        },
    }


@pytest.fixture
def synthetic_frame():
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    cv2.putText(frame, "TEST VIOLATION FRAME", (100, 270),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
    return frame


@pytest.fixture
def synthetic_plate_crop():
    crop = np.zeros((40, 200, 3), dtype=np.uint8)
    cv2.putText(crop, "KA05AB1234", (5, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
    return crop


class TestEvidenceWriter:

    def test_bundle_directory_created(self, writer, sample_record,
                                       synthetic_frame, synthetic_plate_crop):
        dir_path = writer.write_bundle(
            sample_record, synthetic_frame,
            synthetic_plate_crop, synthetic_plate_crop)
        assert dir_path.exists()
        assert dir_path.is_dir()

    def test_metadata_json_created(self, writer, sample_record,
                                    synthetic_frame, synthetic_plate_crop):
        dir_path = writer.write_bundle(
            sample_record, synthetic_frame,
            synthetic_plate_crop, synthetic_plate_crop)
        json_file = dir_path / "violation_metadata.json"
        assert json_file.exists()

    def test_metadata_json_valid_json(self, writer, sample_record,
                                       synthetic_frame, synthetic_plate_crop):
        dir_path = writer.write_bundle(
            sample_record, synthetic_frame,
            synthetic_plate_crop, synthetic_plate_crop)
        json_file = dir_path / "violation_metadata.json"
        with json_file.open() as f:
            data = json.load(f)
        assert data["violation_id"] == "test-viol-001"
        assert data["schema_version"] == "v1"

    def test_evidence_frame_saved(self, writer, sample_record,
                                   synthetic_frame, synthetic_plate_crop):
        dir_path = writer.write_bundle(
            sample_record, synthetic_frame,
            synthetic_plate_crop, synthetic_plate_crop)
        frame_file = dir_path / "evidence_frame.jpg"
        assert frame_file.exists()
        assert frame_file.stat().st_size > 1000  # not empty

    def test_plate_crop_saved(self, writer, sample_record,
                               synthetic_frame, synthetic_plate_crop):
        dir_path = writer.write_bundle(
            sample_record, synthetic_frame,
            synthetic_plate_crop, synthetic_plate_crop)
        plate_file = dir_path / "plate_crop_raw.jpg"
        assert plate_file.exists()

    def test_thumbnail_saved(self, writer, sample_record,
                              synthetic_frame, synthetic_plate_crop):
        dir_path = writer.write_bundle(
            sample_record, synthetic_frame,
            synthetic_plate_crop, synthetic_plate_crop)
        thumb_file = dir_path / "thumbnail.jpg"
        assert thumb_file.exists()

    def test_bundle_with_none_frame(self, writer, sample_record):
        """Should not crash if frame is None."""
        dir_path = writer.write_bundle(sample_record, None, None, None)
        assert dir_path.exists()
        json_file = dir_path / "violation_metadata.json"
        assert json_file.exists()

    def test_dir_name_contains_plate(self, writer, sample_record,
                                      synthetic_frame, synthetic_plate_crop):
        dir_path = writer.write_bundle(
            sample_record, synthetic_frame,
            synthetic_plate_crop, synthetic_plate_crop)
        assert "KA05AB1234" in dir_path.name

    def test_manual_review_enqueue(self, writer):
        writer.enqueue_manual_review(
            {"raw_text": "KA05A81234", "cleaned_text": "KA05AB1234",
             "confidence": 0.45},
            track_id=7, speed_kmph=12.3, camera_id="FP_CAM_001"
        )
        queue_file = writer._manual_review_path
        assert queue_file.exists()
        with queue_file.open() as f:
            line = f.readline()
        data = json.loads(line)
        assert data["track_id"] == 7
        assert data["review_status"] == "pending"

    def test_multiple_violations_separate_directories(
            self, writer, synthetic_frame, synthetic_plate_crop):
        """Each violation must get its own directory."""
        import time
        record1 = {
            "schema_version": "v1", "violation_id": "v1",
            "timestamp": "2026-04-17T07:00:01",
            "timestamp_utc": "2026-04-17T07:00:01+00:00",
            "location": {"camera_id": "C1", "device_id": "D1",
                         "location_name": "L1", "gps_lat": 0.0, "gps_lng": 0.0},
            "vehicle": {"plate_number": "KA05AB0001"},
            "evidence": {"full_frame":"","plate_crop_raw":"",
                         "plate_crop_enhanced":"","thumbnail":""},
        }
        record2 = {
            "schema_version": "v1", "violation_id": "v2",
            "timestamp": "2026-04-17T07:00:02",
            "timestamp_utc": "2026-04-17T07:00:02+00:00",
            "location": {"camera_id": "C1", "device_id": "D1",
                         "location_name": "L1", "gps_lat": 0.0, "gps_lng": 0.0},
            "vehicle": {"plate_number": "MH12DE0002"},
            "evidence": {"full_frame":"","plate_crop_raw":"",
                         "plate_crop_enhanced":"","thumbnail":""},
        }
        d1 = writer.write_bundle(record1, None, None, None)
        d2 = writer.write_bundle(record2, None, None, None)
        assert d1 != d2
