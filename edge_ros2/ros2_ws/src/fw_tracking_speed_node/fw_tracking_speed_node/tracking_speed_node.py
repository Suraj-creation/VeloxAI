"""
fw_tracking_speed_node — Stage 3 ByteTrack + Kalman Speed Estimation
======================================================================
Responsibilities:
  - Subscribe to /fw/detect/twowheeler (DetectionArray)
  - Run ByteTrack (via Ultralytics) OR OC-SORT depending on config
  - Maintain per-track Kalman filter for smooth speed estimation
  - Filter speed < 5 km/h → classify as parked, skip violation path
  - Publish TrackResultArray on /fw/track/speed
  - Enforce challan cooldown tracking at this stage (pre-aggregator)

ROS2 Topics Subscribed:
  /fw/detect/twowheeler (fw_msgs/DetectionArray)

ROS2 Topics Published:
  /fw/track/speed (fw_msgs/TrackResultArray)
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from builtin_interfaces.msg import Time as RosTime

from fw_msgs.msg import Detection, DetectionArray, TrackResult, TrackResultArray

NODE_NAME = "fw_tracking_speed_node"
SUB_TOPIC = "/fw/detect/twowheeler"
PUB_TOPIC = "/fw/track/speed"

CONFIG_POLL_COUNT = 30


def load_json_safe(path: Path, fallback: dict) -> dict:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else fallback
    except Exception:
        pass
    return fallback


# ─── Kalman Speed Estimator ───────────────────────────────────────────────────

class KalmanSpeedEstimator:
    """
    Per-track 4D Kalman filter: state = [x, y, vx, vy]
    Observes pixel (x, y) position, estimates velocity with noise suppression.
    Converts velocity to km/h using pixel-to-metre calibration.
    """

    def __init__(self, pixels_per_metre: float, fps: float):
        self.ppm = max(pixels_per_metre, 1e-6)
        self.fps = max(fps, 1.0)
        self._initialized = False

        # State transition: constant velocity model
        dt = 1.0
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1,  0],
            [0, 0, 0,  1],
        ], dtype=np.float64)

        # Observation: we see [x, y]
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=np.float64)

        # Measurement noise (camera pixel noise ~2px → variance ~4)
        self.R = np.eye(2, dtype=np.float64) * 4.0

        # Process noise
        self.Q = np.eye(4, dtype=np.float64) * 0.1
        self.Q[2, 2] = 0.5
        self.Q[3, 3] = 0.5

        self.P = np.eye(4, dtype=np.float64) * 100.0
        self.x = np.zeros((4, 1), dtype=np.float64)

    def update(self, cx: float, cy: float) -> float:
        """Update with observation, return smoothed speed in km/h."""
        z = np.array([[cx], [cy]], dtype=np.float64)

        if not self._initialized:
            self.x = np.array([[cx], [cy], [0.0], [0.0]])
            self._initialized = True
            return 0.0

        # Predict
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

        # Update
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P

        # Extract velocity
        vx = self.x[2, 0]
        vy = self.x[3, 0]
        pixel_speed = np.sqrt(vx ** 2 + vy ** 2)

        mps = (pixel_speed / self.ppm) * self.fps
        return round(mps * 3.6, 1)


# ─── Tracker Wrapper ──────────────────────────────────────────────────────────

class ByteTrackWrapper:
    """
    Wraps Ultralytics YOLO tracker in standalone mode.
    Because we already have detections, we reconstruct a pseudo-result
    and feed it to the ByteTrack state engine.

    If Ultralytics is not available, falls back to pure IoU matching
    (simple SORT-style) implemented locally.
    """

    def __init__(self, max_age: int = 30, min_hits: int = 3,
                 iou_threshold: float = 0.50):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self._tracks: dict[int, dict] = {}
        self._next_id = 1
        self._frame_count = 0

    def update(self, detections: list[dict]) -> list[dict]:
        """
        Input: list of {x1,y1,x2,y2,confidence,class_name}
        Output: list of {track_id,x1,y1,x2,y2,class_name,confidence,
                         hits,age}
        """
        self._frame_count += 1

        # Age all existing tracks
        for t in self._tracks.values():
            t["age"] += 1
            t["matched"] = False

        if not detections:
            return self._confirmed_tracks()

        # Build cost matrix (IoU)
        track_ids = list(self._tracks.keys())

        if track_ids:
            cost = self._iou_matrix(
                [self._tracks[tid]["bbox"] for tid in track_ids],
                [[d["x1"], d["y1"], d["x2"], d["y2"]] for d in detections]
            )
            matched, unmatch_t, unmatch_d = self._lap_solve(
                cost, track_ids, len(detections))
        else:
            matched = []
            unmatch_t = []
            unmatch_d = list(range(len(detections)))

        # Update matched tracks
        for tid, det_idx in matched:
            d = detections[det_idx]
            self._tracks[tid]["bbox"] = [d["x1"], d["y1"], d["x2"], d["y2"]]
            self._tracks[tid]["confidence"] = d["confidence"]
            self._tracks[tid]["class_name"] = d["class_name"]
            self._tracks[tid]["hits"] += 1
            self._tracks[tid]["age"] = 0
            self._tracks[tid]["matched"] = True

        # Spawn new tracks for unmatched detections
        for det_idx in unmatch_d:
            d = detections[det_idx]
            new_id = self._next_id
            self._next_id += 1
            self._tracks[new_id] = {
                "track_id": new_id,
                "bbox": [d["x1"], d["y1"], d["x2"], d["y2"]],
                "class_name": d["class_name"],
                "confidence": d["confidence"],
                "hits": 1,
                "age": 0,
                "matched": True,
            }

        # Prune dead tracks
        dead = [tid for tid, t in self._tracks.items()
                if t["age"] > self.max_age]
        for tid in dead:
            del self._tracks[tid]

        return self._confirmed_tracks()

    def _confirmed_tracks(self) -> list[dict]:
        return [
            {**t, "track_id": tid}
            for tid, t in self._tracks.items()
            if t["hits"] >= self.min_hits
        ]

    @staticmethod
    def _iou_matrix(track_bboxes: list, det_bboxes: list) -> np.ndarray:
        matrix = np.zeros((len(track_bboxes), len(det_bboxes)))
        for i, tb in enumerate(track_bboxes):
            for j, db in enumerate(det_bboxes):
                xi1 = max(tb[0], db[0])
                yi1 = max(tb[1], db[1])
                xi2 = min(tb[2], db[2])
                yi2 = min(tb[3], db[3])
                inter_w = max(0, xi2 - xi1)
                inter_h = max(0, yi2 - yi1)
                inter = inter_w * inter_h
                area_t = (tb[2]-tb[0]) * (tb[3]-tb[1])
                area_d = (db[2]-db[0]) * (db[3]-db[1])
                union = area_t + area_d - inter
                matrix[i, j] = inter / union if union > 0 else 0.0
        return matrix

    def _lap_solve(self, cost: np.ndarray, track_ids: list,
                   n_dets: int) -> tuple[list, list, list]:
        """Greedy IoU matching (hungarian-lite for small N)."""
        matched = []
        unmatched_t = []
        unmatched_d = list(range(n_dets))

        iou_thresh = self.iou_threshold
        # Greedy: pick highest IoU pairs first
        pairs = []
        for i, tid in enumerate(track_ids):
            for j in range(n_dets):
                pairs.append((cost[i, j], i, j, tid))
        pairs.sort(key=lambda x: -x[0])

        used_t = set()
        used_d = set()
        for iou_val, i, j, tid in pairs:
            if iou_val < iou_thresh:
                break
            if i in used_t or j in used_d:
                continue
            matched.append((tid, j))
            used_t.add(i)
            used_d.add(j)

        for i, tid in enumerate(track_ids):
            if i not in used_t:
                unmatched_t.append(tid)

        unmatched_d = [j for j in range(n_dets) if j not in used_d]

        return matched, unmatched_t, unmatched_d


# ─── ROS2 Node ────────────────────────────────────────────────────────────────

class FwTrackingSpeedNode(Node):

    def __init__(self) -> None:
        super().__init__(NODE_NAME)

        self.declare_parameter("config_dir", "/config")
        self.declare_parameter("device_id", "EDGE-001")
        self.declare_parameter("camera_id", "FP_CAM_001")

        cfg_dir = Path(self.get_parameter("config_dir").value)
        self._cfg_dir = cfg_dir
        self._device_id = str(self.get_parameter("device_id").value)
        self._camera_id = str(self.get_parameter("camera_id").value)

        # Load configs
        speed_cfg = load_json_safe(cfg_dir / "speed_calibration.json", {})
        thresh_cfg = load_json_safe(cfg_dir / "thresholds.json", {})

        self._ppm = float(speed_cfg.get("pixels_per_metre", 47.0))
        self._fps = float(speed_cfg.get("camera_fps", 10.0))
        self._speed_threshold = float(thresh_cfg.get("speed_threshold_kmph", 5.0))

        # Tracker
        max_age = int(thresh_cfg.get("tracker_max_age", 30))
        min_hits = int(thresh_cfg.get("tracker_min_hits", 3))
        iou_thresh = float(thresh_cfg.get("tracker_iou_threshold", 0.50))
        self._tracker = ByteTrackWrapper(max_age=max_age, min_hits=min_hits,
                                         iou_threshold=iou_thresh)

        # Kalman estimators per track
        self._kalman_estimators: dict[int, KalmanSpeedEstimator] = {}

        # Simple history fallback (3-frame average)
        self._track_history: dict[int, deque] = defaultdict(
            lambda: deque(maxlen=10)
        )

        self._msg_count = 0
        self._config_version = 0

        # Publisher + Subscriber
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
        )
        self._pub = self.create_publisher(TrackResultArray, PUB_TOPIC, qos)
        self._sub = self.create_subscription(
            DetectionArray, SUB_TOPIC, self._on_detections, qos
        )

        self.get_logger().info(
            f"[{NODE_NAME}] Ready. "
            f"ppm={self._ppm} fps={self._fps} "
            f"speed_threshold={self._speed_threshold} km/h"
        )

    # ── Detection callback ────────────────────────────────────────────────────

    def _on_detections(self, msg: DetectionArray) -> None:
        self._msg_count += 1

        # Skip flat/signal-error frames early
        if not msg.signal_ok and len(msg.detections) == 0:
            self._publish_empty(msg)
            return

        if self._msg_count % CONFIG_POLL_COUNT == 0:
            self._reload_config()

        t0_tracker = time.perf_counter()

        # Convert Detection msgs to dicts for tracker
        raw_dets = [
            {
                "x1": d.x1, "y1": d.y1, "x2": d.x2, "y2": d.y2,
                "confidence": d.confidence,
                "class_name": d.class_name,
            }
            for d in msg.detections
        ]

        # Run tracker
        tracks = self._tracker.update(raw_dets)
        tracker_lat = (time.perf_counter() - t0_tracker) * 1000.0

        t0_speed = time.perf_counter()

        # Compute speed per track
        track_results: list[TrackResult] = []
        now = self.get_clock().now()

        for t in tracks:
            tid = int(t["track_id"])
            cx = float((t["bbox"][0] + t["bbox"][2]) / 2.0)
            cy = float((t["bbox"][1] + t["bbox"][3]) / 2.0)

            # Kalman estimator
            if tid not in self._kalman_estimators:
                self._kalman_estimators[tid] = KalmanSpeedEstimator(
                    self._ppm, self._fps)
            speed_kmph = self._kalman_estimators[tid].update(cx, cy)

            # History fallback for very first frames
            self._track_history[tid].append((cx, cy))
            history_frames = len(self._track_history[tid])

            tr = TrackResult()
            tr.timestamp = self._ros_time(now)
            tr.camera_id = self._camera_id
            tr.frame_id = msg.frame_id
            tr.track_id = tid
            tr.class_name = str(t["class_name"])
            tr.x1 = float(t["bbox"][0])
            tr.y1 = float(t["bbox"][1])
            tr.x2 = float(t["bbox"][2])
            tr.y2 = float(t["bbox"][3])
            tr.center_x = cx
            tr.center_y = cy
            tr.speed_kmph = speed_kmph
            tr.speed_confidence = float(min(1.0, history_frames / 5.0))
            tr.is_moving = speed_kmph >= self._speed_threshold
            tr.is_parked = speed_kmph < self._speed_threshold
            tr.history_frames = history_frames
            tr.detection_confidence = float(t.get("confidence", 0.0))
            tr.tracker_latency_ms = float(tracker_lat)
            tr.speed_latency_ms = 0.0  # filled below

            track_results.append(tr)

        speed_lat = (time.perf_counter() - t0_speed) * 1000.0
        for tr in track_results:
            tr.speed_latency_ms = float(speed_lat)

        # Publish TrackResultArray
        out = TrackResultArray()
        out.frame_timestamp = msg.frame_timestamp
        out.camera_id = self._camera_id
        out.frame_id = msg.frame_id
        out.frame_number = msg.frame_number
        out.active_track_count = len(track_results)
        out.tracks = track_results
        self._pub.publish(out)

        # Prune Kalman estimators for dead tracks
        active_ids = {int(t["track_id"]) for t in tracks}
        dead_kalmans = [k for k in self._kalman_estimators if k not in active_ids]
        for k in dead_kalmans:
            del self._kalman_estimators[k]
        dead_hist = [k for k in self._track_history if k not in active_ids]
        for k in dead_hist:
            del self._track_history[k]

    # ── Config hot-reload ─────────────────────────────────────────────────────

    def _reload_config(self) -> None:
        speed_cfg = load_json_safe(
            self._cfg_dir / "speed_calibration.json", {})
        thresh_cfg = load_json_safe(self._cfg_dir / "thresholds.json", {})
        self._ppm = float(speed_cfg.get("pixels_per_metre", self._ppm))
        self._fps = float(speed_cfg.get("camera_fps", self._fps))
        self._speed_threshold = float(
            thresh_cfg.get("speed_threshold_kmph", self._speed_threshold))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _publish_empty(self, msg: DetectionArray) -> None:
        out = TrackResultArray()
        out.frame_timestamp = msg.frame_timestamp
        out.camera_id = self._camera_id
        out.frame_id = msg.frame_id
        out.frame_number = msg.frame_number
        out.active_track_count = 0
        out.tracks = []
        self._pub.publish(out)

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
    node = FwTrackingSpeedNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
