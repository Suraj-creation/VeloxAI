"""
fw_ros2_mqtt_bridge — Cloud bridge for AWS IoT Core and backend ingest APIs.

The edge runtime keeps its ROS2 pipeline local and uses this node as the
single cloud egress point. It publishes backend-compatible JSON to MQTT
topics and can also mirror the same payloads to the deployed ingest API so
the current AWS dashboard path works even before IoT rules are provisioned.
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
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy

from fw_msgs.msg import RuntimeHealth, ViolationCandidate, ViolationConfirmed

from fw_ros2_mqtt_bridge.http_sink import HttpIngestClient
from fw_ros2_mqtt_bridge.payloads import (
    build_live_payload,
    build_telemetry_payload,
    build_violation_payload,
    resolve_runtime_config,
)

try:
    import paho.mqtt.client as mqtt

    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

NODE_NAME = "fw_ros2_mqtt_bridge"

CONFIRMED_SUB = "/fw/violation/confirmed"
CANDIDATE_SUB = "/fw/violation/candidate"
HEALTH_SUB = "/fw/health/runtime"

SPOOL_TTL_HOURS = 72
MAX_SPOOL_RECORDS = 5000

DELIVERED = "delivered"
RETRY = "retry"
DROP = "drop"
HOLD = "hold"


def load_json_safe(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return fallback


class DeliverySpool:
    """
    SQLite-backed spool for MQTT and HTTP deliveries.
    Rows stay on disk until they are acknowledged or intentionally dropped.
    """

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS spool (
                    spool_id    TEXT PRIMARY KEY,
                    event_id    TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    attempts    INTEGER DEFAULT 0
                )
                """
            )
            self._ensure_column("sink", "TEXT NOT NULL DEFAULT 'mqtt'")
            self._ensure_column("target", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("qos", "INTEGER NOT NULL DEFAULT 1")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON spool(created_at)")
            self._conn.commit()

    def _ensure_column(self, name: str, definition: str) -> None:
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(spool)").fetchall()
        }
        if name not in cols:
            self._conn.execute(f"ALTER TABLE spool ADD COLUMN {name} {definition}")

    def enqueue(
        self,
        event_id: str,
        sink: str,
        target: str,
        payload: dict[str, Any],
        qos: int = 1,
    ) -> str:
        spool_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO spool (
                    spool_id, event_id, sink, target, payload, created_at, attempts, qos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    spool_id,
                    event_id,
                    sink,
                    target,
                    json.dumps(payload),
                    created_at,
                    0,
                    int(qos),
                ),
            )
            self._conn.commit()
        return spool_id

    def pending(self, limit: int = 200) -> list[tuple[Any, ...]]:
        with self._lock:
            return self._conn.execute(
                """
                SELECT spool_id, event_id, sink, target, payload, created_at, attempts, qos
                FROM spool
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def mark_delivered(self, spool_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM spool WHERE spool_id = ?", (spool_id,))
            self._conn.commit()

    def increment_attempts(self, spool_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE spool SET attempts = attempts + 1 WHERE spool_id = ?",
                (spool_id,),
            )
            self._conn.commit()

    def evict_old(
        self,
        ttl_hours: int = SPOOL_TTL_HOURS,
        max_records: int = MAX_SPOOL_RECORDS,
    ) -> int:
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=ttl_hours)).isoformat()
        evicted = 0
        with self._lock:
            cursor = self._conn.execute("DELETE FROM spool WHERE created_at < ?", (cutoff,))
            evicted += int(cursor.rowcount)
            total = int(self._conn.execute("SELECT COUNT(*) FROM spool").fetchone()[0])
            if total > max_records:
                excess = total - max_records
                self._conn.execute(
                    """
                    DELETE FROM spool
                    WHERE spool_id IN (
                        SELECT spool_id FROM spool ORDER BY created_at ASC LIMIT ?
                    )
                    """,
                    (excess,),
                )
                evicted += excess
            self._conn.commit()
        return evicted

    def depth(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM spool").fetchone()[0])


class MqttSpool(DeliverySpool):
    """
    Backward-compatible wrapper kept for the older unit tests.
    """

    def enqueue(self, event_id: str, topic: str, payload: dict[str, Any]) -> str:  # type: ignore[override]
        return super().enqueue(
            event_id=event_id,
            sink="mqtt",
            target=topic,
            payload=payload,
            qos=1,
        )


class FwMqttClient:
    """
    Lightweight MQTT wrapper with TLS, reconnect backoff, and thread-safe publish.
    """

    def __init__(self, cfg: dict[str, Any], on_connect_cb=None, on_disconnect_cb=None):
        self._cfg = cfg
        self._on_connect_cb = on_connect_cb
        self._on_disconnect_cb = on_disconnect_cb
        self._connected = False
        self._client: Optional["mqtt.Client"] = None
        self._loop_started = False

        if PAHO_AVAILABLE:
            self._client = mqtt.Client(
                client_id=cfg.get("client_id", f"fw-edge-{uuid.uuid4().hex[:8]}"),
                clean_session=True,
            )
            self._client.reconnect_delay_set(min_delay=1, max_delay=30)
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._configure_tls()

    def _configure_tls(self) -> None:
        if self._client is None:
            return

        cert_dir = Path(str(self._cfg.get("cert_dir", "")))
        ca_path = cert_dir / str(self._cfg.get("ca_cert", "rootCA.pem"))
        cert_path = cert_dir / str(self._cfg.get("device_cert", "cert.pem"))
        key_path = cert_dir / str(self._cfg.get("private_key", "private.key"))

        if ca_path.exists() and cert_path.exists() and key_path.exists():
            self._client.tls_set(
                ca_certs=str(ca_path),
                certfile=str(cert_path),
                keyfile=str(key_path),
            )

    def connect(self) -> bool:
        if self._client is None:
            return False

        host = str(self._cfg.get("broker_host", "localhost")).strip()
        port = int(self._cfg.get("broker_port", 1883))
        keep_alive = int(self._cfg.get("keep_alive", 60))
        try:
            self._client.connect_async(host, port, keepalive=keep_alive)
            if not self._loop_started:
                self._client.loop_start()
                self._loop_started = True
            return True
        except Exception as exc:
            logging.warning("[MQTTClient] connect_async failed: %s", exc)
            return False

    def reconnect(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.reconnect()
            return True
        except Exception as exc:
            logging.warning("[MQTTClient] reconnect failed: %s", exc)
            return False

    def publish(self, topic: str, payload: dict[str, Any], qos: int = 1) -> bool:
        if not self._connected or self._client is None:
            return False
        try:
            result = self._client.publish(topic, json.dumps(payload), qos=qos)
            return result.rc == 0
        except Exception as exc:
            logging.warning("[MQTTClient] publish failed: %s", exc)
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _on_connect(self, client, userdata, flags, rc, properties=None) -> None:
        self._connected = rc == 0
        if self._on_connect_cb:
            self._on_connect_cb(rc)

    def _on_disconnect(self, client, userdata, rc, properties=None) -> None:
        self._connected = False
        if self._on_disconnect_cb:
            self._on_disconnect_cb(rc)

    def disconnect(self) -> None:
        if self._client is None:
            return
        try:
            if self._loop_started:
                self._client.loop_stop()
                self._loop_started = False
            self._client.disconnect()
        except Exception:
            pass


class FwRos2MqttBridge(Node):
    def __init__(self) -> None:
        super().__init__(NODE_NAME)

        self.declare_parameter("config_dir", "/config")
        self.declare_parameter("device_id", "EDGE-001")
        self.declare_parameter("camera_id", "FP_CAM_001")
        self.declare_parameter("site_id", "SITE-001")
        self.declare_parameter("spool_db_path", "/violations/mqtt_spool.db")

        cfg_dir = Path(str(self.get_parameter("config_dir").value))
        self._device_id = str(self.get_parameter("device_id").value)
        self._camera_id = str(self.get_parameter("camera_id").value)
        configured_site_id = str(self.get_parameter("site_id").value)
        spool_db = Path(str(self.get_parameter("spool_db_path").value))

        raw_cfg = load_json_safe(cfg_dir / "mqtt_config.json", {})
        self._cfg = resolve_runtime_config(cfg_dir, raw_cfg)
        self._site_id = str(self._cfg.get("site_id", configured_site_id))

        topic_prefix = str(self._cfg.get("mqtt_topic_prefix", "footwatch")).strip("/")
        topic_root = f"{topic_prefix}/{self._site_id}/{self._camera_id}"
        self._topic_violation = f"{topic_root}/{self._cfg['mqtt_violation_topic']}"
        self._topic_telemetry = f"{topic_root}/{self._cfg['mqtt_telemetry_topic']}"
        self._topic_live = f"{topic_root}/{self._cfg['mqtt_live_topic']}"

        self._spool = DeliverySpool(spool_db)
        self._replay_lock = threading.Lock()
        self._replaying = False

        self._mqtt_enabled = bool(self._cfg.get("mqtt_enabled", True))
        self._http = HttpIngestClient(
            base_url=str(self._cfg.get("http_ingest_base_url", "")),
            api_key=str(self._cfg.get("http_ingest_api_key", "")),
            timeout_sec=float(self._cfg.get("http_timeout_sec", 10.0)),
            enabled=bool(self._cfg.get("http_enabled", True)),
        )

        self._mqtt: Optional[FwMqttClient] = None
        if self._mqtt_enabled and PAHO_AVAILABLE:
            self._mqtt = FwMqttClient(
                self._cfg,
                on_connect_cb=self._on_mqtt_connect,
                on_disconnect_cb=self._on_mqtt_disconnect,
            )
            self._mqtt.connect()
        elif self._mqtt_enabled:
            self.get_logger().warn(
                f"[{NODE_NAME}] paho-mqtt is not installed; MQTT delivery is disabled."
            )
            self._mqtt_enabled = False

        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=20,
        )

        self._confirmed_sub = self.create_subscription(
            ViolationConfirmed, CONFIRMED_SUB, self._on_confirmed, qos
        )
        self._candidate_sub = self.create_subscription(
            ViolationCandidate, CANDIDATE_SUB, self._on_candidate, qos
        )
        self._health_sub = self.create_subscription(
            RuntimeHealth, HEALTH_SUB, self._on_health, qos
        )

        self.create_timer(10.0, self._ensure_mqtt_connection)
        self.create_timer(15.0, self._replay_spool)
        self.create_timer(3600.0, self._evict_spool)

        self.get_logger().info(
            f"[{NODE_NAME}] Ready. mqtt_enabled={self._mqtt_enabled} "
            f"http_enabled={self._http.enabled} spool_depth={self._spool.depth()} "
            f"topic_telemetry={self._topic_telemetry} "
            f"topic_violation={self._topic_violation}"
        )

    def _on_confirmed(self, msg: ViolationConfirmed) -> None:
        payload = build_violation_payload(msg)
        event_id = str(payload["violation_id"])

        if self._mqtt_enabled:
            self._queue_delivery(
                event_id=event_id,
                sink="mqtt",
                target=self._topic_violation,
                payload=payload,
                qos=1,
            )

        if self._http.enabled:
            self._queue_delivery(
                event_id=event_id,
                sink="http",
                target="/v1/violations",
                payload=payload,
                qos=1,
            )

    def _on_health(self, msg: RuntimeHealth) -> None:
        payload = build_telemetry_payload(msg)
        event_id = f"telemetry-{payload['camera_id']}-{payload['timestamp']}"

        if self._mqtt_enabled:
            self._queue_delivery(
                event_id=event_id,
                sink="mqtt",
                target=self._topic_telemetry,
                payload=payload,
                qos=0,
            )

        if self._http.enabled:
            self._queue_delivery(
                event_id=event_id,
                sink="http",
                target="/v1/telemetry",
                payload=payload,
                qos=0,
            )

    def _on_candidate(self, msg: ViolationCandidate) -> None:
        if not self._mqtt_enabled or self._mqtt is None:
            return
        payload = build_live_payload(msg)
        if self._mqtt.is_connected:
            self._mqtt.publish(self._topic_live, payload, qos=0)

    def _queue_delivery(
        self,
        event_id: str,
        sink: str,
        target: str,
        payload: dict[str, Any],
        qos: int,
    ) -> None:
        spool_id = self._spool.enqueue(
            event_id=event_id,
            sink=sink,
            target=target,
            payload=payload,
            qos=qos,
        )
        outcome = self._attempt_delivery(sink=sink, target=target, payload=payload, qos=qos)
        self._handle_outcome(spool_id=spool_id, event_id=event_id, sink=sink, outcome=outcome)

    def _attempt_delivery(
        self,
        sink: str,
        target: str,
        payload: dict[str, Any],
        qos: int,
    ) -> str:
        if sink == "mqtt":
            if not target:
                return DROP
            if self._mqtt is None:
                return HOLD
            if not self._mqtt.is_connected:
                return HOLD
            return DELIVERED if self._mqtt.publish(target, payload, qos=qos) else RETRY

        if sink == "http":
            if target.endswith("/v1/violations"):
                result = self._http.post_violation(payload)
            elif target.endswith("/v1/telemetry"):
                result = self._http.post_telemetry(payload)
            else:
                result = self._http.deliver(target, payload)

            if result.ok:
                return DELIVERED

            if result.retryable:
                self.get_logger().warn(
                    f"[{NODE_NAME}] HTTP delivery retry scheduled "
                    f"path={target} status={result.status_code} body={result.body}"
                )
                return RETRY

            self.get_logger().error(
                f"[{NODE_NAME}] Dropping non-retryable HTTP event "
                f"path={target} status={result.status_code} body={result.body}"
            )
            return DROP

        return DROP

    def _handle_outcome(self, spool_id: str, event_id: str, sink: str, outcome: str) -> None:
        if outcome == DELIVERED:
            self._spool.mark_delivered(spool_id)
            return

        if outcome == RETRY:
            self._spool.increment_attempts(spool_id)
            return

        if outcome == DROP:
            self._spool.mark_delivered(spool_id)
            self.get_logger().warn(
                f"[{NODE_NAME}] Dropped undeliverable event event_id={event_id} sink={sink}"
            )

    def _ensure_mqtt_connection(self) -> None:
        if not self._mqtt_enabled or self._mqtt is None:
            return
        if not self._mqtt.is_connected:
            self._mqtt.reconnect()

    def _replay_spool(self) -> None:
        with self._replay_lock:
            if self._replaying:
                return
            self._replaying = True
        threading.Thread(target=self._do_replay, daemon=True).start()

    def _do_replay(self) -> None:
        delivered = 0
        retries = 0
        try:
            for row in self._spool.pending():
                spool_id, event_id, sink, target, payload_str, created_at, attempts, qos = row
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    self._spool.mark_delivered(spool_id)
                    continue

                outcome = self._attempt_delivery(
                    sink=str(sink),
                    target=str(target),
                    payload=payload,
                    qos=int(qos),
                )
                if outcome == DELIVERED:
                    self._spool.mark_delivered(str(spool_id))
                    delivered += 1
                elif outcome == RETRY:
                    self._spool.increment_attempts(str(spool_id))
                    retries += 1
                elif outcome == DROP:
                    self._spool.mark_delivered(str(spool_id))

            if delivered or retries:
                self.get_logger().info(
                    f"[{NODE_NAME}] Replay cycle complete delivered={delivered} retried={retries}"
                )
        finally:
            self._replaying = False

    def _evict_spool(self) -> None:
        evicted = self._spool.evict_old()
        if evicted:
            self.get_logger().info(
                f"[{NODE_NAME}] Evicted {evicted} stale spool rows."
            )

    def _on_mqtt_connect(self, rc: int) -> None:
        if rc == 0:
            self.get_logger().info(f"[{NODE_NAME}] MQTT connected.")
            self._replay_spool()
        else:
            self.get_logger().warn(f"[{NODE_NAME}] MQTT connect failed rc={rc}")

    def _on_mqtt_disconnect(self, rc: int) -> None:
        self.get_logger().warn(
            f"[{NODE_NAME}] MQTT disconnected rc={rc}. Cloud events will remain queued."
        )

    def destroy_node(self) -> None:
        if self._mqtt is not None:
            self._mqtt.disconnect()
        super().destroy_node()


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
