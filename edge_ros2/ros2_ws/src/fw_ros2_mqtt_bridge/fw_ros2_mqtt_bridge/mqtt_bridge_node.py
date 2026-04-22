"""
fw_ros2_mqtt_bridge — MQTT Bridge to AWS IoT Core
==================================================
Responsibilities:
  - Subscribe to /fw/violation/confirmed (fw_msgs/ViolationConfirmed)
  - Subscribe to /fw/health/runtime (fw_msgs/RuntimeHealth)
  - Publish to AWS IoT Core MQTT topics:
      footwatch/{site_id}/{camera_id}/violation
      footwatch/{site_id}/{camera_id}/health
      footwatch/{site_id}/{camera_id}/live
  - Persistent retry spool: if MQTT offline, queues to SQLite
  - Replay spooled events on reconnect (ordered, with TTL eviction)
  - Idempotency: include event_id in payload so backend can dedup

ROS2 Topics Subscribed:
  /fw/violation/confirmed  (fw_msgs/ViolationConfirmed)
  /fw/violation/candidate  (fw_msgs/ViolationCandidate)
  /fw/health/runtime       (fw_msgs/RuntimeHealth)

Config:
  /config/mqtt_config.json — broker host, port, certs, site_id, TLS settings
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

from fw_msgs.msg import ViolationConfirmed, ViolationCandidate, RuntimeHealth

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

NODE_NAME = "fw_ros2_mqtt_bridge"

CONFIRMED_SUB = "/fw/violation/confirmed"
CANDIDATE_SUB = "/fw/violation/candidate"
HEALTH_SUB = "/fw/health/runtime"

SCHEMA_VERSION = "v1"
SPOOL_TTL_HOURS = 72      # drop undelivered events older than this
MAX_SPOOL_RECORDS = 5000  # max pending events before oldest are dropped


def load_json_safe(path: Path, fallback: dict) -> dict:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return fallback


# ─── Persistent MQTT Spool ────────────────────────────────────────────────────

class MqttSpool:
    """
    SQLite-backed at-least-once delivery spool.
    Events are written before attempting MQTT publish.
    On successful delivery the row is deleted.
    At startup, all undelivered rows are replayed in order.
    """

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS spool (
                    spool_id    TEXT PRIMARY KEY,
                    event_id    TEXT NOT NULL,
                    topic       TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    attempts    INTEGER DEFAULT 0
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created ON spool(created_at)")
            self._conn.commit()

    def enqueue(self, event_id: str, topic: str, payload: dict) -> str:
        spool_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO spool(spool_id,event_id,topic,payload,created_at)"
                " VALUES (?,?,?,?,?)",
                (spool_id, event_id, topic, json.dumps(payload), ts),
            )
            self._conn.commit()
        return spool_id

    def mark_delivered(self, spool_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM spool WHERE spool_id=?",
                               (spool_id,))
            self._conn.commit()

    def increment_attempts(self, spool_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE spool SET attempts=attempts+1 WHERE spool_id=?",
                (spool_id,))
            self._conn.commit()

    def pending(self) -> list[tuple]:
        """Return all pending rows ordered by created_at ASC."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT spool_id,event_id,topic,payload,created_at,attempts"
                " FROM spool ORDER BY created_at ASC LIMIT 200"
            ).fetchall()
        return rows

    def evict_old(self, ttl_hours: int = SPOOL_TTL_HOURS,
                  max_records: int = MAX_SPOOL_RECORDS) -> int:
        """Delete records older than TTL or beyond max_records. Returns count evicted."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) -
                  timedelta(hours=ttl_hours)).isoformat()
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM spool WHERE created_at < ?", (cutoff,))
            evicted = cur.rowcount
            # Cap total records
            count = self._conn.execute(
                "SELECT COUNT(*) FROM spool").fetchone()[0]
            if count > max_records:
                excess = count - max_records
                self._conn.execute(
                    "DELETE FROM spool WHERE spool_id IN "
                    "(SELECT spool_id FROM spool ORDER BY created_at ASC LIMIT ?)",
                    (excess,))
                evicted += excess
            self._conn.commit()
        return evicted

    def depth(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM spool").fetchone()[0]


# ─── MQTT Client Wrapper ──────────────────────────────────────────────────────

class FwMqttClient:
    """
    Wraps paho-mqtt with:
      - TLS mutual auth for AWS IoT Core
      - Automatic reconnect with exponential backoff
      - Thread-safe publish
      - Connection state flag
    """

    def __init__(self, cfg: dict, on_connect_cb=None, on_disconnect_cb=None):
        self._cfg = cfg
        self._on_connect_cb = on_connect_cb
        self._on_disconnect_cb = on_disconnect_cb
        self._connected = False
        self._lock = threading.Lock()
        self._client: Optional["mqtt.Client"] = None

        if PAHO_AVAILABLE:
            self._client = mqtt.Client(
                client_id=cfg.get("client_id", f"fw-edge-{uuid.uuid4().hex[:8]}"),
                clean_session=True,
            )
            self._configure_tls()
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect

    def _configure_tls(self) -> None:
        cert_dir = Path(self._cfg.get("cert_dir", "/certs"))
        ca = cert_dir / self._cfg.get("ca_cert", "root-CA.crt")
        cert = cert_dir / self._cfg.get("device_cert", "device.cert.pem")
        key = cert_dir / self._cfg.get("private_key", "device.private.key")

        if ca.exists() and cert.exists() and key.exists():
            self._client.tls_set(
                ca_certs=str(ca),
                certfile=str(cert),
                keyfile=str(key),
            )
        # else: plain MQTT (dev/local broker)

    def connect(self) -> bool:
        if not PAHO_AVAILABLE or self._client is None:
            return False
        try:
            host = self._cfg.get("broker_host", "localhost")
            port = int(self._cfg.get("broker_port", 8883))
            self._client.connect(host, port, keepalive=60)
            self._client.loop_start()
            return True
        except Exception as exc:
            logging.warning(f"[MQTTClient] Connect failed: {exc}")
            return False

    def publish(self, topic: str, payload: dict, qos: int = 1) -> bool:
        if not self._connected or self._client is None:
            return False
        try:
            result = self._client.publish(
                topic, json.dumps(payload), qos=qos)
            return result.rc == 0
        except Exception as exc:
            logging.warning(f"[MQTTClient] Publish failed: {exc}")
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _on_connect(self, client, userdata, flags, rc) -> None:
        self._connected = (rc == 0)
        if self._on_connect_cb:
            self._on_connect_cb(rc)

    def _on_disconnect(self, client, userdata, rc) -> None:
        self._connected = False
        if self._on_disconnect_cb:
            self._on_disconnect_cb(rc)

    def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()


# ─── ROS2 Node ────────────────────────────────────────────────────────────────

class FwRos2MqttBridge(Node):

    def __init__(self) -> None:
        super().__init__(NODE_NAME)

        self.declare_parameter("config_dir", "/config")
        self.declare_parameter("device_id", "EDGE-001")
        self.declare_parameter("camera_id", "FP_CAM_001")
        self.declare_parameter("site_id", "SITE-001")
        self.declare_parameter("spool_db_path", "/violations/mqtt_spool.db")

        cfg_dir = Path(self.get_parameter("config_dir").value)
        self._device_id = str(self.get_parameter("device_id").value)
        self._camera_id = str(self.get_parameter("camera_id").value)
        self._site_id = str(self.get_parameter("site_id").value)
        spool_db = Path(self.get_parameter("spool_db_path").value)

        # Load MQTT config
        mqtt_cfg = load_json_safe(cfg_dir / "mqtt_config.json", {})

        # MQTT topic prefixes
        base = f"footwatch/{self._site_id}/{self._camera_id}"
        self._topic_violation = f"{base}/violation"
        self._topic_health = f"{base}/health"
        self._topic_live = f"{base}/live"

        # Spool
        self._spool = MqttSpool(spool_db)
        pending = self._spool.depth()
        self.get_logger().info(
            f"[{NODE_NAME}] Spool has {pending} undelivered events.")

        # MQTT client
        self._mqtt = FwMqttClient(
            mqtt_cfg,
            on_connect_cb=self._on_mqtt_connect,
            on_disconnect_cb=self._on_mqtt_disconnect,
        )
        self._mqtt.connect()

        self._replay_lock = threading.Lock()
        self._replaying = False

        # QoS
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=20,
        )

        # Subscriptions
        self._confirmed_sub = self.create_subscription(
            ViolationConfirmed, CONFIRMED_SUB, self._on_confirmed, qos)
        self._candidate_sub = self.create_subscription(
            ViolationCandidate, CANDIDATE_SUB, self._on_candidate, qos)
        self._health_sub = self.create_subscription(
            RuntimeHealth, HEALTH_SUB, self._on_health, qos)

        # Periodic spool replay + eviction
        self.create_timer(15.0, self._replay_spool)
        self.create_timer(3600.0, self._evict_spool)

        self.get_logger().info(
            f"[{NODE_NAME}] Ready. "
            f"violation_topic={self._topic_violation} "
            f"connected={self._mqtt.is_connected}"
        )

    # ── Confirmed violation → MQTT ────────────────────────────────────────────

    def _on_confirmed(self, msg: ViolationConfirmed) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "event_id": str(msg.event_id),
            "device_id": str(msg.device_id),
            "camera_id": str(msg.camera_id),
            "ts_utc": str(msg.ts_utc),
            "event_type": str(msg.event_type),
            "speed_kmph": float(msg.speed_kmph),
            "class_name": str(msg.class_name),
            "confidence": float(msg.confidence),
            "plate_text": str(msg.plate_text),
            "ocr_confidence": float(msg.ocr_confidence),
            "gps_lat": float(msg.gps_lat),
            "gps_lng": float(msg.gps_lng),
            "location_name": str(msg.location_name),
            "evidence_uri": str(msg.evidence_uri),
            "pipeline_latency_ms": float(msg.total_pipeline_latency_ms),
        }

        # Spool first (ensures at-least-once even if publish fails)
        spool_id = self._spool.enqueue(
            msg.event_id, self._topic_violation, payload)

        if self._mqtt.is_connected:
            ok = self._mqtt.publish(self._topic_violation, payload, qos=1)
            if ok:
                self._spool.mark_delivered(spool_id)
                self.get_logger().info(
                    f"[{NODE_NAME}] Published violation {msg.event_id}")
            else:
                self._spool.increment_attempts(spool_id)

    # ── Candidate → live topic ────────────────────────────────────────────────

    def _on_candidate(self, msg: ViolationCandidate) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "event_id": str(msg.event_id),
            "camera_id": str(msg.camera_id),
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "event_type": "LIVE_CANDIDATE",
            "plate_text": str(msg.plate_text),
            "speed_kmph": float(msg.speed_kmph),
            "class_name": str(msg.class_name),
            "gps_lat": float(msg.gps_lat),
            "gps_lng": float(msg.gps_lng),
        }
        if self._mqtt.is_connected:
            self._mqtt.publish(self._topic_live, payload, qos=0)

    # ── Health → MQTT ─────────────────────────────────────────────────────────

    def _on_health(self, msg: RuntimeHealth) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "device_id": str(msg.device_id),
            "camera_id": str(msg.camera_id),
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "pipeline_running": bool(msg.pipeline_running),
            "pipeline_fps": float(msg.pipeline_fps),
            "pipeline_latency_ms_p50": float(msg.pipeline_latency_ms_p50),
            "active_tracks": int(msg.active_tracks),
            "violations_session": int(msg.violations_in_session),
            "mqtt_spool_depth": int(msg.mqtt_offline_queue_depth),
            "cpu_percent": float(msg.cpu_percent),
            "memory_used_mb": float(msg.memory_used_mb),
            "cpu_temp_c": float(msg.cpu_temp_celsius),
            "disk_free_gb": float(msg.disk_free_gb),
            "camera_connected": bool(msg.camera_connected),
            "camera_status": str(msg.camera_status),
            "frame_failures": int(msg.frame_failures),
            "reconnects": int(msg.reconnects),
        }

        spool_id = self._spool.enqueue(
            str(uuid.uuid4()), self._topic_health, payload)
        if self._mqtt.is_connected:
            ok = self._mqtt.publish(self._topic_health, payload, qos=0)
            if ok:
                self._spool.mark_delivered(spool_id)

    # ── Spool replay ──────────────────────────────────────────────────────────

    def _replay_spool(self) -> None:
        if not self._mqtt.is_connected:
            return
        with self._replay_lock:
            if self._replaying:
                return
            self._replaying = True

        thread = threading.Thread(target=self._do_replay, daemon=True)
        thread.start()

    def _do_replay(self) -> None:
        try:
            rows = self._spool.pending()
            delivered = 0
            for row in rows:
                spool_id, event_id, topic, payload_str, created_at, attempts = row
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    self._spool.mark_delivered(spool_id)
                    continue

                ok = self._mqtt.publish(topic, payload, qos=1)
                if ok:
                    self._spool.mark_delivered(spool_id)
                    delivered += 1
                else:
                    self._spool.increment_attempts(spool_id)

            if delivered > 0:
                self.get_logger().info(
                    f"[{NODE_NAME}] Replayed {delivered}/{len(rows)} spooled events.")
        finally:
            self._replaying = False

    def _evict_spool(self) -> None:
        evicted = self._spool.evict_old()
        if evicted > 0:
            self.get_logger().info(
                f"[{NODE_NAME}] Evicted {evicted} stale spool entries.")

    # ── MQTT callbacks ────────────────────────────────────────────────────────

    def _on_mqtt_connect(self, rc: int) -> None:
        if rc == 0:
            self.get_logger().info(f"[{NODE_NAME}] MQTT connected.")
            # Immediately trigger a replay
            threading.Thread(target=self._do_replay, daemon=True).start()
        else:
            self.get_logger().warn(
                f"[{NODE_NAME}] MQTT connect failed rc={rc}")

    def _on_mqtt_disconnect(self, rc: int) -> None:
        self.get_logger().warn(
            f"[{NODE_NAME}] MQTT disconnected rc={rc}. "
            "Events will be spooled until reconnect.")

    def destroy_node(self) -> None:
        self.get_logger().info(f"[{NODE_NAME}] Shutting down.")
        self._mqtt.disconnect()
        super().destroy_node()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main(args=None) -> None:
    rclpy.init(args=args)
    node = FwRos2MqttBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
