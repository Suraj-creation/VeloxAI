"""
fw_health_node — System Health Monitor and Publisher
====================================================
Responsibilities:
  - Collect CPU %, memory, temp, disk every 10s
  - Track pipeline FPS from /fw/detect/twowheeler messages
  - Track active track count from /fw/track/speed
  - Track MQTT spool depth from bridge node
  - Publish RuntimeHealth on /fw/health/runtime
  - Expose Prometheus metrics on :9100 (optional)
  - Camera connectivity watchdog: alert if no frames for >30s
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import psutil
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from builtin_interfaces.msg import Time as RosTime

from fw_msgs.msg import (
    DetectionArray, TrackResultArray, ViolationConfirmed, RuntimeHealth)

NODE_NAME = "fw_health_node"
DETECTION_SUB = "/fw/detect/twowheeler"
TRACK_SUB = "/fw/track/speed"
CONFIRMED_SUB = "/fw/violation/confirmed"
HEALTH_PUB = "/fw/health/runtime"

SCHEMA_VERSION = "v1"
HEALTH_PUBLISH_INTERVAL = 10.0   # seconds
CAMERA_TIMEOUT_SEC = 30.0        # alert if no frame in this window


def load_json_safe(path: Path, fallback: dict) -> dict:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return fallback


def get_cpu_temp() -> float:
    """Read Raspberry Pi or Linux CPU temperature."""
    temp_paths = [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/class/hwmon/hwmon0/temp1_input",
    ]
    for p in temp_paths:
        try:
            val = float(open(p).read().strip())
            return round(val / 1000.0, 1)
        except Exception:
            pass
    # macOS fallback
    try:
        import subprocess
        out = subprocess.check_output(
            ["sysctl", "-n", "machdep.xcpm.cpu_thermal_level"],
            timeout=1).decode().strip()
        return float(out)
    except Exception:
        return 0.0


class PrometheusMetrics:
    """Optional Prometheus exporter. No-ops if prometheus_client not installed."""

    def __init__(self, port: int = 9100):
        self._available = False
        try:
            from prometheus_client import (
                Gauge, Counter, Histogram, start_http_server)
            start_http_server(port)
            self._cpu_temp = Gauge("fw_cpu_temp_celsius", "CPU temperature")
            self._cpu_pct = Gauge("fw_cpu_percent", "CPU utilisation")
            self._mem_mb = Gauge("fw_memory_used_mb", "RAM used MB")
            self._disk_gb = Gauge("fw_disk_free_gb", "Disk free GB")
            self._fps = Gauge("fw_pipeline_fps", "Detection loop FPS")
            self._latency = Gauge("fw_pipeline_latency_p50_ms", "Latency P50 ms")
            self._violations = Counter("fw_violations_total", "Total violations")
            self._spool_depth = Gauge("fw_mqtt_spool_depth", "MQTT spool depth")
            self._cam_status = Gauge("fw_camera_connected", "Camera connected 0/1")
            self._available = True
        except ImportError:
            pass

    def update(self, health: "RuntimeHealth") -> None:
        if not self._available:
            return
        self._cpu_temp.set(health.cpu_temp_celsius)
        self._cpu_pct.set(health.cpu_percent)
        self._mem_mb.set(health.memory_used_mb)
        self._disk_gb.set(health.disk_free_gb)
        self._fps.set(health.pipeline_fps)
        self._latency.set(health.pipeline_latency_ms_p50)
        self._spool_depth.set(health.mqtt_offline_queue_depth)
        self._cam_status.set(1 if health.camera_connected else 0)


class FwHealthNode(Node):

    def __init__(self) -> None:
        super().__init__(NODE_NAME)

        self.declare_parameter("config_dir", "/config")
        self.declare_parameter("device_id", "EDGE-001")
        self.declare_parameter("camera_id", "FP_CAM_001")
        self.declare_parameter("prometheus_port", 9100)
        self.declare_parameter("spool_db_path", "/violations/mqtt_spool.db")

        cfg_dir = Path(self.get_parameter("config_dir").value)
        self._device_id = str(self.get_parameter("device_id").value)
        self._camera_id = str(self.get_parameter("camera_id").value)
        prom_port = int(self.get_parameter("prometheus_port").value)
        self._spool_db = Path(self.get_parameter("spool_db_path").value)

        # State trackers
        self._fps_ts: deque[float] = deque(maxlen=50)
        self._latencies: deque[float] = deque(maxlen=50)
        self._active_tracks = 0
        self._violations_session = 0
        self._pipeline_errors = 0

        self._last_frame_ts = time.monotonic()
        self._camera_connected = False
        self._camera_status = "waiting"
        self._signal_mean = 0.0
        self._signal_std = 0.0
        self._frame_failures = 0
        self._reconnects = 0

        # Prometheus
        self._prom = PrometheusMetrics(port=prom_port)

        # QoS
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
        )
        qos_rel = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
        )

        # Subscriptions
        self._det_sub = self.create_subscription(
            DetectionArray, DETECTION_SUB, self._on_detection, qos)
        self._track_sub = self.create_subscription(
            TrackResultArray, TRACK_SUB, self._on_track, qos)
        self._confirmed_sub = self.create_subscription(
            ViolationConfirmed, CONFIRMED_SUB, self._on_confirmed, qos_rel)

        # Publisher
        self._pub = self.create_publisher(RuntimeHealth, HEALTH_PUB, qos_rel)

        # Timer
        self.create_timer(HEALTH_PUBLISH_INTERVAL, self._publish_health)

        self.get_logger().info(
            f"[{NODE_NAME}] Ready. Publishing health every "
            f"{HEALTH_PUBLISH_INTERVAL}s to {HEALTH_PUB}"
        )

    # ── Detection monitor ─────────────────────────────────────────────────────

    def _on_detection(self, msg: DetectionArray) -> None:
        now = time.monotonic()
        self._fps_ts.append(now)
        self._last_frame_ts = now

        self._camera_connected = msg.signal_ok
        if msg.signal_ok:
            self._camera_status = "online"
        else:
            self._camera_status = "signal_flat"

        self._signal_mean = float(msg.signal_mean_luma)
        self._signal_std = float(msg.signal_std_luma)

        if msg.stage1_latency_ms > 0:
            self._latencies.append(float(msg.stage1_latency_ms))

    def _on_track(self, msg: TrackResultArray) -> None:
        self._active_tracks = int(msg.active_track_count)

    def _on_confirmed(self, msg: ViolationConfirmed) -> None:
        self._violations_session += 1

    # ── Health publish ────────────────────────────────────────────────────────

    def _publish_health(self) -> None:
        now = time.monotonic()

        # Camera timeout watchdog
        if now - self._last_frame_ts > CAMERA_TIMEOUT_SEC:
            self._camera_connected = False
            self._camera_status = "disconnected"

        fps = self._compute_fps()
        p50_lat = self._p50_latency()

        # Device metrics
        cpu_pct = float(psutil.cpu_percent(interval=None))
        mem = psutil.virtual_memory()
        mem_mb = float(mem.used / 1024 / 1024)
        cpu_temp = get_cpu_temp()

        disk_gb = 0.0
        for mount_point in ("/home", "/", "C:"):
            try:
                disk = psutil.disk_usage(mount_point)
                disk_gb = float(disk.free / (1024 ** 3))
                break
            except Exception:
                pass

        spool_depth = self._spool_depth()

        msg = RuntimeHealth()
        now_ros = self.get_clock().now()
        msg.timestamp = self._ros_time(now_ros)
        msg.device_id = self._device_id
        msg.camera_id = self._camera_id
        msg.schema_version = SCHEMA_VERSION
        msg.pipeline_running = self._camera_connected
        msg.pipeline_fps = float(fps)
        msg.pipeline_latency_ms_p50 = float(p50_lat)
        msg.active_tracks = int(self._active_tracks)
        msg.violations_in_session = int(self._violations_session)
        msg.mqtt_offline_queue_depth = int(spool_depth)
        msg.cpu_percent = cpu_pct
        msg.memory_used_mb = mem_mb
        msg.cpu_temp_celsius = cpu_temp
        msg.disk_free_gb = disk_gb
        msg.camera_connected = self._camera_connected
        msg.camera_status = self._camera_status
        msg.signal_mean_luma = float(self._signal_mean)
        msg.signal_std_luma = float(self._signal_std)
        msg.frame_failures = int(self._frame_failures)
        msg.reconnects = int(self._reconnects)
        msg.pipeline_errors = int(self._pipeline_errors)

        self._pub.publish(msg)
        self._prom.update(msg)

        self.get_logger().info(
            f"[{NODE_NAME}] Health: "
            f"fps={fps:.1f} temp={cpu_temp}°C cpu={cpu_pct:.0f}% "
            f"mem={mem_mb:.0f}MB disk={disk_gb:.1f}GB "
            f"cam={self._camera_status} spool={spool_depth} "
            f"violations={self._violations_session}"
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _compute_fps(self) -> float:
        if len(self._fps_ts) < 2:
            return 0.0
        elapsed = self._fps_ts[-1] - self._fps_ts[0]
        return (len(self._fps_ts) - 1) / elapsed if elapsed > 0 else 0.0

    def _p50_latency(self) -> float:
        if not self._latencies:
            return 0.0
        import numpy as np
        return float(np.median(list(self._latencies)))

    def _spool_depth(self) -> int:
        try:
            import sqlite3
            if self._spool_db.exists():
                conn = sqlite3.connect(str(self._spool_db))
                count = conn.execute(
                    "SELECT COUNT(*) FROM spool").fetchone()[0]
                conn.close()
                return int(count)
        except Exception:
            pass
        return 0

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
    node = FwHealthNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
