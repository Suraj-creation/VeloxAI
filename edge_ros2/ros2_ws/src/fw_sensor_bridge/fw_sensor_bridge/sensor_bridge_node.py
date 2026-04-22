"""
fw_sensor_bridge — Camera Ingress Node
=======================================
The single camera owner in the pipeline. Publishes raw frames
to /fw/camera/frame as CompressedImage. Every other node that
needs pixel data MUST subscribe to this topic — no node opens
the camera device directly except this one.

Responsibilities:
  - Open USB camera, RTSP stream, or replay video file
  - Publish sensor_msgs/CompressedImage on /fw/camera/frame at target FPS
  - Embed a UUID frame_id in header.frame_id for cross-node correlation
  - Publish frame quality metadata (signal_ok, luma stats)
  - Auto-reconnect on camera loss
  - Config hot-reload every 30 frames

Published Topics:
  /fw/camera/frame        (sensor_msgs/CompressedImage)
  /fw/camera/diagnostics  (std_msgs/String — JSON signal metadata)

Parameters:
  config_dir    /config
  camera_id     FP_CAM_001
  preview_path  /violations/.preview.jpg   (atomic JPEG for dashboard)
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import (QoSProfile, QoSReliabilityPolicy,
                        QoSHistoryPolicy, QoSDurabilityPolicy)
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
from builtin_interfaces.msg import Time as RosTime

NODE_NAME = "fw_sensor_bridge"
FRAME_TOPIC = "/fw/camera/frame"
DIAG_TOPIC = "/fw/camera/diagnostics"

CONFIG_POLL_FRAMES = 30
RECONNECT_FAILURES = 8        # Reopen capture after this many consecutive failures


def load_json_safe(path: Path, fallback: dict) -> dict:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else fallback
    except Exception:
        pass
    return fallback


def check_frame_signal(frame: np.ndarray) -> tuple[bool, float, float]:
    """
    Returns (is_ok, mean_luma, std_luma).
    Flat frame detection: std < 4 OR mean < 5 OR mean > 250.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = float(np.mean(gray))
    std = float(np.std(gray))
    ok = not (std < 4.0 or mean < 5.0 or mean > 250.0)
    return ok, mean, std


def export_preview(frame: np.ndarray, path: Path) -> None:
    """Atomic JPEG write — tmp file then rename to prevent partial reads."""
    tmp = path.with_suffix(".tmp.jpg")
    try:
        ok = cv2.imwrite(str(tmp), frame,
                         [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ok:
            tmp.replace(path)
    except Exception:
        pass


def open_capture(source: str | int, width: int, height: int,
                 buffer_size: int = 1) -> cv2.VideoCapture:
    """
    Open camera with backend fallback. Tries platform-specific
    backends (V4L2, GStreamer, DSHOW) before the default.
    Sets buffer_size=1 for minimal latency.
    """
    backends: list[int | None] = [None]
    if isinstance(source, int):
        for attr in ("CAP_V4L2", "CAP_GSTREAMER", "CAP_DSHOW", "CAP_MSMF"):
            val = getattr(cv2, attr, None)
            if val is not None:
                backends.insert(0, val)

    for backend in backends:
        cap = (cv2.VideoCapture(source, backend)
               if backend is not None
               else cv2.VideoCapture(source))
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
            cap.set(cv2.CAP_PROP_BUFFERSIZE, float(buffer_size))
            return cap
        cap.release()

    return cv2.VideoCapture(source)


class FwSensorBridge(Node):

    def __init__(self) -> None:
        super().__init__(NODE_NAME)

        # ── Parameters ───────────────────────────────────────────────────────
        self.declare_parameter("config_dir", "/config")
        self.declare_parameter("camera_id", "FP_CAM_001")
        self.declare_parameter("preview_path", "/violations/.preview.jpg")
        self.declare_parameter("jpeg_quality", 75)

        cfg_dir = Path(self.get_parameter("config_dir").value)
        self._camera_id = str(self.get_parameter("camera_id").value)
        self._preview_path = Path(self.get_parameter("preview_path").value)
        self._jpeg_quality = int(self.get_parameter("jpeg_quality").value)
        self._cfg_dir = cfg_dir

        # ── Load config ───────────────────────────────────────────────────────
        self._lab_cfg = load_json_safe(cfg_dir / "camera_lab.json", {})
        self._config_version: int = self._lab_cfg.get("config_version", 0)

        # Camera source settings
        self._source = self._resolve_source()
        self._width = int(self._lab_cfg.get("previewWidth", 960))
        self._height = int(self._lab_cfg.get("previewHeight", 540))
        self._target_fps = int(self._lab_cfg.get("targetFps", 10))

        # ── Runtime state ─────────────────────────────────────────────────────
        self._frame_count = 0
        self._consecutive_failures = 0
        self._reconnects = 0
        self._last_good_frame_ts = time.monotonic()

        # FPS and latency tracking
        self._fps_ts: deque[float] = deque(maxlen=30)
        self._pub_latencies: deque[float] = deque(maxlen=50)

        # ── Open camera ───────────────────────────────────────────────────────
        self._cap = open_capture(self._source, self._width, self._height)
        if self._cap.isOpened():
            self.get_logger().info(
                f"[{NODE_NAME}] Camera opened: {self._source}")
        else:
            self.get_logger().warn(
                f"[{NODE_NAME}] Camera not available: {self._source}. "
                "Will retry every tick.")

        # ── QoS for camera frames ─────────────────────────────────────────────
        # Best-effort + keep-last-1 for live video (never buffer old frames)
        frame_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )
        # Reliable for diagnostics
        diag_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
        )

        self._frame_pub = self.create_publisher(
            CompressedImage, FRAME_TOPIC, frame_qos)
        self._diag_pub = self.create_publisher(
            String, DIAG_TOPIC, diag_qos)

        # ── capture timer ─────────────────────────────────────────────────────
        period = 1.0 / max(self._target_fps, 1)
        self._timer = self.create_timer(period, self._capture_and_publish)

        self.get_logger().info(
            f"[{NODE_NAME}] Ready. topic={FRAME_TOPIC} "
            f"fps={self._target_fps} source={self._source}"
        )

    # ── Source resolution ──────────────────────────────────────────────────────

    def _resolve_source(self) -> str | int:
        mode = str(self._lab_cfg.get("sourceMode", "device")).lower()
        val = str(self._lab_cfg.get("sourceValue", "0")).strip()
        if mode == "rtsp":
            return val
        if mode == "file":
            return val
        return int(val) if val.isdigit() else 0

    # ── Config hot-reload ──────────────────────────────────────────────────────

    def _reload_config_if_changed(self) -> None:
        cfg = load_json_safe(self._cfg_dir / "camera_lab.json", {})
        ver = cfg.get("config_version", 0)
        if ver == self._config_version:
            return

        self._config_version = ver
        old_source = self._source
        self._lab_cfg = cfg
        self._source = self._resolve_source()
        new_width = int(cfg.get("previewWidth", self._width))
        new_height = int(cfg.get("previewHeight", self._height))
        new_fps = int(cfg.get("targetFps", self._target_fps))

        source_changed = old_source != self._source
        shape_changed = (new_width != self._width
                         or new_height != self._height)

        self._width = new_width
        self._height = new_height

        if source_changed or shape_changed:
            self._cap.release()
            self._cap = open_capture(self._source, self._width, self._height)
            self._reconnects += 1
            self.get_logger().info(
                f"[{NODE_NAME}] Config reloaded → reopened camera: "
                f"{self._source}"
            )

        if new_fps != self._target_fps:
            self._target_fps = new_fps
            self._timer.cancel()
            self._timer = self.create_timer(
                1.0 / max(self._target_fps, 1),
                self._capture_and_publish)

    # ── Main capture loop ──────────────────────────────────────────────────────

    def _capture_and_publish(self) -> None:
        if self._frame_count % CONFIG_POLL_FRAMES == 0:
            self._reload_config_if_changed()

        t0 = time.perf_counter()

        # Attempt reconnect if camera not open
        if not self._cap.isOpened():
            self._publish_diagnostics_only(
                signal_ok=False, mean=0.0, std=0.0,
                status="camera_disconnected")
            self._cap = open_capture(
                self._source, self._width, self._height)
            if self._cap.isOpened():
                self._reconnects += 1
                self.get_logger().info(
                    f"[{NODE_NAME}] Camera reconnected (attempt "
                    f"#{self._reconnects})"
                )
            return

        ok, frame = self._cap.read()
        if not ok:
            self._consecutive_failures += 1
            if self._consecutive_failures >= RECONNECT_FAILURES:
                self.get_logger().warn(
                    f"[{NODE_NAME}] {self._consecutive_failures} "
                    "consecutive failures — reopening capture."
                )
                self._cap.release()
                self._cap = open_capture(
                    self._source, self._width, self._height)
                self._reconnects += 1
                self._consecutive_failures = 0
            self._publish_diagnostics_only(
                signal_ok=False, mean=0.0, std=0.0,
                status="waiting_frame")
            return

        self._consecutive_failures = 0
        self._frame_count += 1
        self._fps_ts.append(time.monotonic())
        self._last_good_frame_ts = time.monotonic()

        # Signal quality
        signal_ok, mean_luma, std_luma = check_frame_signal(frame)

        # Generate frame UUID — used by ALL downstream nodes for correlation
        frame_id = str(uuid.uuid4())

        # ── Encode and publish CompressedImage ────────────────────────────────
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        ok_enc, jpeg_buf = cv2.imencode(".jpg", frame, encode_params)

        if ok_enc:
            msg = CompressedImage()
            now = self.get_clock().now()
            msg.header.stamp = self._ros_stamp(now)
            # Pack frame_id + signal metadata into header.frame_id
            # Format: "<uuid>|<camera_id>|<signal_ok>|<mean>|<std>|<frame_num>"
            msg.header.frame_id = (
                f"{frame_id}|{self._camera_id}|"
                f"{'1' if signal_ok else '0'}|"
                f"{mean_luma:.2f}|{std_luma:.2f}|{self._frame_count}"
            )
            msg.format = "jpeg"
            msg.data = jpeg_buf.tobytes()
            self._frame_pub.publish(msg)

        latency_ms = (time.perf_counter() - t0) * 1000.0
        self._pub_latencies.append(latency_ms)

        # ── Diagnostics JSON ──────────────────────────────────────────────────
        fps = self._current_fps()
        p50 = float(np.median(list(self._pub_latencies))) \
            if self._pub_latencies else 0.0

        diag = {
            "camera_id": self._camera_id,
            "frame_id": frame_id,
            "frame_number": self._frame_count,
            "signal_ok": signal_ok,
            "signal_mean_luma": round(mean_luma, 1),
            "signal_std_luma": round(std_luma, 1),
            "fps": round(fps, 1),
            "publish_latency_ms_p50": round(p50, 1),
            "reconnects": self._reconnects,
            "camera_status": "online" if signal_ok else "signal_flat",
        }
        diag_msg = String()
        diag_msg.data = json.dumps(diag)
        self._diag_pub.publish(diag_msg)

        # ── Preview export (async) ────────────────────────────────────────────
        if self._frame_count % 5 == 0:    # export every 5th frame
            threading.Thread(
                target=export_preview,
                args=(frame.copy(), self._preview_path),
                daemon=True,
            ).start()

        # Periodic log
        if self._frame_count % 50 == 0:
            self.get_logger().info(
                f"[{NODE_NAME}] frame={self._frame_count} "
                f"fps={fps:.1f} latency_p50={p50:.1f}ms "
                f"signal={'OK' if signal_ok else 'FLAT'} "
                f"reconnects={self._reconnects}"
            )

    def _publish_diagnostics_only(self, signal_ok: bool,
                                   mean: float, std: float,
                                   status: str) -> None:
        diag = {
            "camera_id": self._camera_id,
            "frame_number": self._frame_count,
            "signal_ok": signal_ok,
            "signal_mean_luma": mean,
            "signal_std_luma": std,
            "camera_status": status,
            "fps": 0.0,
        }
        msg = String()
        msg.data = json.dumps(diag)
        self._diag_pub.publish(msg)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _current_fps(self) -> float:
        if len(self._fps_ts) < 2:
            return 0.0
        elapsed = self._fps_ts[-1] - self._fps_ts[0]
        return (len(self._fps_ts) - 1) / elapsed if elapsed > 0 else 0.0

    @staticmethod
    def _ros_stamp(stamp) -> RosTime:
        ros_t = RosTime()
        t_ns = stamp.nanoseconds
        ros_t.sec = int(t_ns // 1_000_000_000)
        ros_t.nanosec = int(t_ns % 1_000_000_000)
        return ros_t

    def destroy_node(self) -> None:
        self.get_logger().info(f"[{NODE_NAME}] Shutting down.")
        if self._cap:
            self._cap.release()
        super().destroy_node()


# ── Helpers exported for other nodes ──────────────────────────────────────────

def parse_frame_header(header_frame_id: str) -> dict:
    """
    Parse the packed header.frame_id string published by fw_sensor_bridge.
    Returns: {frame_id, camera_id, signal_ok, mean_luma, std_luma, frame_number}
    """
    try:
        parts = header_frame_id.split("|")
        return {
            "frame_id": parts[0],
            "camera_id": parts[1],
            "signal_ok": parts[2] == "1",
            "mean_luma": float(parts[3]),
            "std_luma": float(parts[4]),
            "frame_number": int(parts[5]),
        }
    except Exception:
        return {
            "frame_id": header_frame_id,
            "camera_id": "unknown",
            "signal_ok": True,
            "mean_luma": 128.0,
            "std_luma": 30.0,
            "frame_number": 0,
        }


# ── Entry point ────────────────────────────────────────────────────────────────

def main(args=None) -> None:
    rclpy.init(args=args)
    node = FwSensorBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
