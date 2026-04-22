"""
fw_violation_aggregator — Stage 7: Evidence Package + Confirmed Violation
=========================================================================
Responsibilities:
  - Subscribe to /fw/camera/frame (CompressedImage from fw_sensor_bridge)
  - Subscribe to /fw/track/speed and /fw/plate/ocr
  - Correlate track + OCR results by track_id
  - Apply dual cooldown deduplication (per track_id AND per plate_text)
  - Apply gates: speed >= threshold AND ocr_conf >= min_conf AND format_valid
  - Build evidence bundle: annotated frame crop plate images + metadata JSON
    (frame is taken from the ring buffer keyed by frame_id)
  - Publish ViolationConfirmed on /fw/violation/confirmed
  - Publish ViolationCandidate on /fw/violation/candidate (fast path, monitoring)
  - Write violation_metadata.json to /violations/{timestamp}_{plate}/ directory
  - Queue low-confidence plates to manual_review_queue.jsonl

ROS2 Topics Subscribed:
  /fw/camera/frame (sensor_msgs/CompressedImage — fw_sensor_bridge)
  /fw/track/speed  (fw_msgs/TrackResultArray)
  /fw/plate/ocr    (fw_msgs/PlateOcr)

ROS2 Topics Published:
  /fw/violation/candidate  (fw_msgs/ViolationCandidate)
  /fw/violation/confirmed  (fw_msgs/ViolationConfirmed)
"""

from __future__ import annotations

import json
import time
import uuid
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from builtin_interfaces.msg import Time as RosTime
from sensor_msgs.msg import CompressedImage

from fw_msgs.msg import (
    TrackResultArray,
    TrackResult,
    PlateOcr,
    ViolationCandidate,
    ViolationConfirmed,
)
from fw_sensor_bridge.sensor_bridge_node import parse_frame_header

NODE_NAME = "fw_violation_aggregator"
TRACK_SUB = "/fw/track/speed"
OCR_SUB = "/fw/plate/ocr"
FRAME_SUB = "/fw/camera/frame"
CANDIDATE_PUB = "/fw/violation/candidate"
CONFIRMED_PUB = "/fw/violation/confirmed"

SCHEMA_VERSION = "v1"
MANUAL_REVIEW_FILE = "manual_review_queue.jsonl"
FRAME_BUFFER_SIZE = 8   # ring buffer depth: enough to cover inter-node jitter


def load_json_safe(path: Path, fallback: dict) -> dict:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return fallback


# ─── Frame ring buffer ────────────────────────────────────────────────────────

class FrameRingBuffer:
    """Thread-safe ring buffer: frame_id → (BGR frame, monotonic_ts)."""

    def __init__(self, capacity: int = FRAME_BUFFER_SIZE):
        self._buf: OrderedDict[str, tuple[np.ndarray, float]] = OrderedDict()
        self._cap = capacity
        self._lock = threading.Lock()

    def put(self, frame_id: str, frame: np.ndarray) -> None:
        with self._lock:
            if frame_id in self._buf:
                self._buf.move_to_end(frame_id)
            else:
                if len(self._buf) >= self._cap:
                    self._buf.popitem(last=False)
            self._buf[frame_id] = (frame, time.monotonic())

    def get(self, frame_id: str) -> Optional[np.ndarray]:
        with self._lock:
            entry = self._buf.get(frame_id)
            return entry[0].copy() if entry is not None else None

    def latest(self) -> Optional[np.ndarray]:
        with self._lock:
            if not self._buf:
                return None
            return next(reversed(self._buf.values()))[0].copy()


# ─── Evidence Bundle Writer ───────────────────────────────────────────────────

class EvidenceWriter:
    """
    Creates structured evidence bundle for each confirmed violation.

    violations/
      2025-01-15_14-23-07_KA05AB1234/
        evidence_frame.jpg
        plate_crop_raw.jpg
        plate_crop_enhanced.jpg
        thumbnail.jpg
        violation_metadata.json
    """

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        base_dir.mkdir(parents=True, exist_ok=True)
        self._manual_review_path = base_dir / MANUAL_REVIEW_FILE

    def write_bundle(
        self,
        record: dict,
        full_frame: Optional[np.ndarray],
        plate_crop_raw: Optional[np.ndarray],
        plate_crop_enhanced: Optional[np.ndarray],
    ) -> Path:
        """Write all evidence files. Returns bundle directory path."""
        ts = record["timestamp"].replace(":", "-").replace("T", "_")[:19]
        plate = record["vehicle"]["plate_number"] or "UNKNOWN"
        dir_name = f"{ts}_{plate}"
        dir_path = self._base_dir / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)

        def _save(img: Optional[np.ndarray], fname: str) -> str:
            if img is None or img.size == 0:
                return ""
            path = dir_path / fname
            tmp = path.with_suffix(".tmp.jpg")
            ok = cv2.imwrite(str(tmp), img,
                             [cv2.IMWRITE_JPEG_QUALITY, 90])
            if ok:
                tmp.replace(path)
                return str(path)
            return ""

        frame_path = _save(full_frame, "evidence_frame.jpg")
        raw_path = _save(plate_crop_raw, "plate_crop_raw.jpg")
        enhanced_path = _save(plate_crop_enhanced, "plate_crop_enhanced.jpg")

        # Thumbnail
        if full_frame is not None:
            thumb = cv2.resize(full_frame, (320, 240))
            _save(thumb, "thumbnail.jpg")

        # Update evidence paths in record
        record["evidence"]["full_frame"] = frame_path
        record["evidence"]["plate_crop_raw"] = raw_path
        record["evidence"]["plate_crop_enhanced"] = enhanced_path
        record["evidence"]["thumbnail"] = str(dir_path / "thumbnail.jpg")

        # Write metadata JSON
        json_path = dir_path / "violation_metadata.json"
        tmp_json = json_path.with_suffix(".tmp.json")
        with tmp_json.open("w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        tmp_json.replace(json_path)

        return dir_path

    def enqueue_manual_review(self, ocr_result: dict, track_id: int,
                              speed_kmph: float, camera_id: str) -> None:
        """Append low-confidence plate to manual review queue."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "camera_id": camera_id,
            "track_id": track_id,
            "speed_kmph": speed_kmph,
            "raw_text": ocr_result.get("raw_text", ""),
            "cleaned_text": ocr_result.get("cleaned_text", ""),
            "confidence": ocr_result.get("confidence", 0.0),
            "review_status": "pending",
        }
        try:
            with self._manual_review_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


# ─── OCR result cache for correlation ─────────────────────────────────────────

class OcrCorrelationBuffer:
    """
    Rolling buffer mapping (track_id) → latest PlateOcr result.
    TTL-evicts stale entries to prevent memory growth.
    """

    def __init__(self, ttl_seconds: float = 5.0):
        self._buf: dict[int, tuple[PlateOcr, float]] = {}
        self._ttl = ttl_seconds

    def put(self, ocr_msg: PlateOcr) -> None:
        self._buf[ocr_msg.track_id] = (ocr_msg, time.monotonic())

    def get(self, track_id: int) -> Optional[PlateOcr]:
        if track_id not in self._buf:
            return None
        msg, ts = self._buf[track_id]
        if time.monotonic() - ts > self._ttl:
            del self._buf[track_id]
            return None
        return msg

    def evict_stale(self) -> None:
        now = time.monotonic()
        dead = [k for k, (_, ts) in self._buf.items()
                if now - ts > self._ttl]
        for k in dead:
            del self._buf[k]


# ─── ROS2 Node ────────────────────────────────────────────────────────────────

class FwViolationAggregator(Node):

    def __init__(self) -> None:
        super().__init__(NODE_NAME)

        self.declare_parameter("config_dir", "/config")
        self.declare_parameter("violations_dir", "/violations")
        self.declare_parameter("device_id", "EDGE-001")
        self.declare_parameter("camera_id", "FP_CAM_001")

        cfg_dir = Path(self.get_parameter("config_dir").value)
        violations_dir = Path(self.get_parameter("violations_dir").value)
        self._device_id = str(self.get_parameter("device_id").value)
        self._camera_id = str(self.get_parameter("camera_id").value)
        self._cfg_dir = cfg_dir

        # Load configs
        thresh_cfg = load_json_safe(cfg_dir / "thresholds.json", {})
        camera_cfg = load_json_safe(cfg_dir / "camera_lab.json", {})

        self._speed_threshold = float(
            thresh_cfg.get("speed_threshold_kmph", 5.0))
        self._min_ocr_conf = float(
            thresh_cfg.get("min_ocr_confidence", 0.65))
        self._cooldown_sec = int(
            thresh_cfg.get("cooldown_sec", 60))
        self._manual_review_conf = float(
            thresh_cfg.get("manual_review_min_conf", 0.40))
        self._gps_lat = float(camera_cfg.get("gpsLat", 0.0))
        self._gps_lng = float(camera_cfg.get("gpsLng", 0.0))
        self._location_name = str(
            camera_cfg.get("locationName", "Unknown Location"))
        self._config_version = 0

        # State
        self._last_violation_by_track: dict[int, float] = {}
        self._last_violation_by_plate: dict[str, float] = {}
        self._violation_count = 0
        self._ocr_buf = OcrCorrelationBuffer(ttl_seconds=5.0)
        self._evidence_writer = EvidenceWriter(violations_dir)

        # Frame ring buffer — populated from /fw/camera/frame
        self._frame_buf = FrameRingBuffer(FRAME_BUFFER_SIZE)

        # QoS
        frame_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )
        reliable_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # Publishers
        self._candidate_pub = self.create_publisher(
            ViolationCandidate, CANDIDATE_PUB, reliable_qos)
        self._confirmed_pub = self.create_publisher(
            ViolationConfirmed, CONFIRMED_PUB, reliable_qos)

        # Subscribers — frame sub FIRST so buffer is ready
        self._frame_sub = self.create_subscription(
            CompressedImage, FRAME_SUB, self._on_frame, frame_qos)
        self._track_sub = self.create_subscription(
            TrackResultArray, TRACK_SUB, self._on_tracks, reliable_qos)
        self._ocr_sub = self.create_subscription(
            PlateOcr, OCR_SUB, self._on_ocr, reliable_qos)

        # Periodic eviction and config reload
        self.create_timer(10.0, self._housekeeping)

        self.get_logger().info(
            f"[{NODE_NAME}] Ready. "
            f"speed≥{self._speed_threshold}km/h "
            f"ocr_conf≥{self._min_ocr_conf} "
            f"cooldown={self._cooldown_sec}s"
        )

    # ── Frame callback: buffer decoded frames ────────────────────────────────

    def _on_frame(self, msg: CompressedImage) -> None:
        meta = parse_frame_header(msg.header.frame_id)
        if not meta["signal_ok"]:
            return
        buf = np.frombuffer(msg.data, dtype=np.uint8)
        frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if frame is not None:
            self._frame_buf.put(meta["frame_id"], frame)

    # ── OCR message buffer ────────────────────────────────────────────────────

    def _on_ocr(self, msg: PlateOcr) -> None:
        self._ocr_buf.put(msg)

    # ── Track message: main decision logic ───────────────────────────────────

    def _on_tracks(self, msg: TrackResultArray) -> None:
        # Fetch frame by exact frame_id, fallback to latest
        frame = (self._frame_buf.get(msg.frame_id)
                 or self._frame_buf.latest())

        now = time.monotonic()
        ts_utc = datetime.now(timezone.utc).isoformat()

        for track in msg.tracks:
            if not track.is_moving:
                continue

            # Correlate OCR
            ocr_msg = self._ocr_buf.get(track.track_id)
            if ocr_msg is None:
                continue  # no OCR result yet for this track

            # Validation gates
            plate_text = str(ocr_msg.cleaned_text)
            ocr_conf = float(ocr_msg.ocr_confidence)
            format_valid = bool(ocr_msg.format_valid)

            # Low-conf → manual review queue, don't issue auto-challan
            if ocr_conf >= self._manual_review_conf and not format_valid:
                self._evidence_writer.enqueue_manual_review(
                    {"raw_text": ocr_msg.raw_text,
                     "cleaned_text": plate_text,
                     "confidence": ocr_conf},
                    track.track_id, track.speed_kmph, self._camera_id,
                )

            if not format_valid or ocr_conf < self._min_ocr_conf:
                continue

            # Cooldown check — per track and per plate
            last_t = max(
                float(self._last_violation_by_track.get(track.track_id, 0.0)),
                float(self._last_violation_by_plate.get(plate_text, 0.0)),
            )
            if now - last_t < self._cooldown_sec:
                continue

            # ── All gates passed → confirmed violation ────────────────────────
            self._last_violation_by_track[track.track_id] = now
            self._last_violation_by_plate[plate_text] = now
            self._violation_count += 1

            event_id = str(uuid.uuid4())
            t_start = time.perf_counter()

            record = self._build_record(
                event_id, ts_utc, track, ocr_msg, plate_text, ocr_conf)

            # Extract plate crop images from buffered frame
            plate_crop_raw: Optional[np.ndarray] = None
            plate_crop_enhanced: Optional[np.ndarray] = None
            if (frame is not None and ocr_msg.plate_found
                    and ocr_msg.plate_x2 > ocr_msg.plate_x1
                    and ocr_msg.plate_y2 > ocr_msg.plate_y1):
                fh, fw = frame.shape[:2]
                px1 = max(0, int(ocr_msg.plate_x1))
                py1 = max(0, int(ocr_msg.plate_y1))
                px2 = min(fw - 1, int(ocr_msg.plate_x2))
                py2 = min(fh - 1, int(ocr_msg.plate_y2))
                plate_crop_raw = frame[py1:py2, px1:px2].copy()
                # Re-apply CLAHE for enhanced crop (consistent with OCR node)
                if plate_crop_raw.size > 0:
                    gray = cv2.cvtColor(plate_crop_raw, cv2.COLOR_BGR2GRAY)
                    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
                    enh = clahe.apply(gray)
                    plate_crop_enhanced = cv2.cvtColor(enh, cv2.COLOR_GRAY2BGR)

            # Evidence bundle (async — never blocks ROS spin loop)
            t_evidence = threading.Thread(
                target=self._write_evidence_async,
                args=(record, frame, plate_crop_raw, plate_crop_enhanced,
                      track, ocr_msg, event_id),
                daemon=True,
            )
            t_evidence.start()

            # Publish candidate first (fast path)
            cand = self._build_candidate_msg(
                event_id, track, plate_text, ocr_conf, ts_utc)
            self._candidate_pub.publish(cand)

            total_ms = (time.perf_counter() - t_start) * 1000.0

            # Publish confirmed (evidence paths will be empty until async finishes)
            conf_msg = self._build_confirmed_msg(
                event_id, ts_utc, track, plate_text, ocr_conf,
                float(track.detection_confidence), total_ms, record
            )
            self._confirmed_pub.publish(conf_msg)

            self.get_logger().info(
                f"[{NODE_NAME}] VIOLATION #{self._violation_count} "
                f"plate={plate_text} speed={track.speed_kmph:.1f}km/h "
                f"ocr_conf={ocr_conf:.2f} track_id={track.track_id} "
                f"event_id={event_id}"
            )

    # ── Evidence bundle async ─────────────────────────────────────────────────

    def _write_evidence_async(
        self,
        record: dict,
        frame: Optional[np.ndarray],
        plate_raw: Optional[np.ndarray],
        plate_enhanced: Optional[np.ndarray],
        track: TrackResult,
        ocr_msg: PlateOcr,
        event_id: str,
    ) -> None:
        try:
            # Annotate frame with violation overlay
            if frame is not None:
                annotated = self._annotate_violation_frame(
                    frame, track, ocr_msg, event_id)
            else:
                annotated = None

            self._evidence_writer.write_bundle(
                record, annotated, plate_raw, plate_enhanced)
        except Exception as exc:
            self.get_logger().error(
                f"[{NODE_NAME}] Evidence write failed for {event_id}: {exc}")

    def _annotate_violation_frame(
        self,
        frame: np.ndarray,
        track: TrackResult,
        ocr_msg: PlateOcr,
        event_id: str,
    ) -> np.ndarray:
        annotated = frame.copy()
        x1, y1, x2, y2 = (int(track.x1), int(track.y1),
                           int(track.x2), int(track.y2))

        # Red vehicle box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 3)

        # Plate box (green)
        if ocr_msg.plate_found:
            px1, py1 = int(ocr_msg.plate_x1), int(ocr_msg.plate_y1)
            px2, py2 = int(ocr_msg.plate_x2), int(ocr_msg.plate_y2)
            cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 255, 0), 2)

        labels = [
            f"VIOLATION | {track.class_name.upper()}",
            f"Plate: {ocr_msg.cleaned_text}  conf:{ocr_msg.ocr_confidence:.2f}",
            f"Speed: {track.speed_kmph:.1f} km/h",
            f"ID: {event_id[:8]}",
        ]
        for i, label in enumerate(labels):
            cv2.putText(annotated, label, (x1, max(18, y1 - 8 - i * 22)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

        ts_label = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(annotated, f"{self._camera_id} | {ts_label}",
                    (10, annotated.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        return annotated

    # ── Record builders ───────────────────────────────────────────────────────

    def _build_record(self, event_id: str, ts_utc: str,
                      track: TrackResult, ocr_msg: PlateOcr,
                      plate_text: str, ocr_conf: float) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "violation_id": event_id,
            "timestamp": datetime.now().isoformat(),
            "timestamp_utc": ts_utc,

            "location": {
                "camera_id": self._camera_id,
                "device_id": self._device_id,
                "location_name": self._location_name,
                "gps_lat": self._gps_lat,
                "gps_lng": self._gps_lng,
            },

            "vehicle": {
                "plate_number": plate_text,
                "plate_ocr_confidence": round(ocr_conf, 3),
                "plate_format_valid": True,
                "vehicle_class": str(track.class_name),
                "estimated_speed_kmph": round(float(track.speed_kmph), 2),
                "track_id": int(track.track_id),
                "detection_confidence": round(float(track.detection_confidence), 3),
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
                "device_id": self._device_id,
                "schema_version": SCHEMA_VERSION,
                "pushed_to_cloud": False,
                "push_timestamp": None,
                "pipeline_latency_ms": None,
            },
        }

    def _build_candidate_msg(self, event_id: str, track: TrackResult,
                             plate_text: str, ocr_conf: float,
                             ts_utc: str) -> ViolationCandidate:
        msg = ViolationCandidate()
        now = self.get_clock().now()
        msg.timestamp = self._ros_time(now)
        msg.camera_id = self._camera_id
        msg.frame_id = track.frame_id
        msg.event_id = event_id
        msg.track_id = track.track_id
        msg.class_name = str(track.class_name)
        msg.speed_kmph = float(track.speed_kmph)
        msg.plate_text = plate_text
        msg.ocr_confidence = float(ocr_conf)
        msg.plate_format_valid = True
        msg.gps_lat = self._gps_lat
        msg.gps_lng = self._gps_lng
        msg.location_name = self._location_name
        return msg

    def _build_confirmed_msg(
        self, event_id: str, ts_utc: str, track: TrackResult,
        plate_text: str, ocr_conf: float, det_conf: float,
        total_ms: float, record: dict,
    ) -> ViolationConfirmed:
        msg = ViolationConfirmed()
        now = self.get_clock().now()
        msg.timestamp = self._ros_time(now)
        msg.schema_version = SCHEMA_VERSION
        msg.event_id = event_id
        msg.device_id = self._device_id
        msg.camera_id = self._camera_id
        msg.ts_utc = ts_utc
        msg.event_type = "FOOTPATH_ENCROACHMENT"
        msg.track_id = int(track.track_id)
        msg.class_name = str(track.class_name)
        msg.speed_kmph = float(track.speed_kmph)
        msg.confidence = det_conf
        msg.plate_text = plate_text
        msg.ocr_confidence = float(ocr_conf)
        msg.plate_format_valid = True
        msg.gps_lat = self._gps_lat
        msg.gps_lng = self._gps_lng
        msg.location_name = self._location_name
        msg.evidence_dir = ""
        msg.evidence_uri = ""
        msg.total_pipeline_latency_ms = total_ms
        msg.pushed_to_cloud = False
        return msg

    # ── Periodic housekeeping ─────────────────────────────────────────────────

    def _housekeeping(self) -> None:
        self._ocr_buf.evict_stale()

        # Evict old cooldown entries (older than 10× cooldown)
        now = time.monotonic()
        limit = self._cooldown_sec * 10
        stale_tracks = [k for k, v in self._last_violation_by_track.items()
                        if now - v > limit]
        for k in stale_tracks:
            del self._last_violation_by_track[k]
        stale_plates = [k for k, v in self._last_violation_by_plate.items()
                        if now - v > limit]
        for k in stale_plates:
            del self._last_violation_by_plate[k]

        # Reload thresholds
        thresh_cfg = load_json_safe(self._cfg_dir / "thresholds.json", {})
        self._speed_threshold = float(
            thresh_cfg.get("speed_threshold_kmph", self._speed_threshold))
        self._min_ocr_conf = float(
            thresh_cfg.get("min_ocr_confidence", self._min_ocr_conf))
        self._cooldown_sec = int(
            thresh_cfg.get("cooldown_sec", self._cooldown_sec))

        self.get_logger().debug(
            f"[{NODE_NAME}] housekeeping done. "
            f"violations={self._violation_count} "
            f"active_plate_cooldowns={len(self._last_violation_by_plate)}"
        )

    @staticmethod
    def _ros_time(stamp) -> RosTime:
        ros_t = RosTime()
        t_ns = stamp.nanoseconds
        ros_t.sec = int(t_ns // 1_000_000_000)
        ros_t.nanosec = int(t_ns % 1_000_000_000)
        return ros_t


# ─── Entry point ──────────────────────────────────────────────────────────────

def main(args=None) -> None:
    rclpy.init(args=args)
    node = FwViolationAggregator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
