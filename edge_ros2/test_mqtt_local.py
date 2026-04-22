"""
Local cloud smoke test for edge_ros2.

Modes:
  --mode mock     Print the exact payloads that would be sent.
  --mode backend  POST telemetry + violation payloads to the ingest API.
  --mode aws      Publish the same payloads to AWS IoT Core over TLS.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "ros2_ws" / "src" / "fw_ros2_mqtt_bridge"))

from fw_ros2_mqtt_bridge.http_sink import HttpIngestClient
from fw_ros2_mqtt_bridge.payloads import (
    build_telemetry_payload,
    build_violation_payload,
    resolve_runtime_config,
)

try:
    import paho.mqtt.client as mqtt

    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False


class FakeStamp:
    def __init__(self, sec: int, nanosec: int = 0) -> None:
        self.sec = sec
        self.nanosec = nanosec


def load_config() -> dict:
    with (ROOT / "config" / "mqtt_config.json").open("r", encoding="utf-8") as handle:
        raw_cfg = json.load(handle)
    return resolve_runtime_config(ROOT / "config", raw_cfg)


def sample_health_msg() -> SimpleNamespace:
    now = int(time.time())
    return SimpleNamespace(
        timestamp=FakeStamp(now),
        device_id="pi-001",
        camera_id="FP_CAM_001",
        pipeline_running=True,
        pipeline_fps=11.8,
        pipeline_latency_ms_p50=48.2,
        reconnects=0,
        frame_failures=0,
        camera_connected=True,
        camera_status="online",
        cpu_percent=37.5,
        memory_used_mb=624.0,
        cpu_temp_celsius=55.0,
        disk_free_gb=19.3,
        active_tracks=2,
        mqtt_offline_queue_depth=0,
    )


def sample_violation_msg() -> SimpleNamespace:
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    return SimpleNamespace(
        event_id=f"vio-{int(time.time())}",
        timestamp=FakeStamp(int(time.time())),
        ts_utc=now_iso,
        device_id="pi-001",
        camera_id="FP_CAM_001",
        event_type="FOOTPATH_ENCROACHMENT",
        track_id=101,
        class_name="motorcycle",
        speed_kmph=22.8,
        confidence=0.91,
        plate_text="KA05AB1234",
        ocr_confidence=0.87,
        plate_format_valid=True,
        gps_lat=12.9716,
        gps_lng=77.5946,
        location_name="Sample Junction",
        evidence_dir="violations/sample",
        evidence_uri="s3://footwatch-dev-evidence-769213333967/sample.jpg",
        total_pipeline_latency_ms=145.6,
    )


def print_payloads() -> tuple[dict, dict]:
    telemetry = build_telemetry_payload(sample_health_msg())
    violation = build_violation_payload(sample_violation_msg())
    print("\nTelemetry payload")
    print("=" * 60)
    print(json.dumps(telemetry, indent=2))
    print("\nViolation payload")
    print("=" * 60)
    print(json.dumps(violation, indent=2))
    return telemetry, violation


def run_backend_test(cfg: dict) -> None:
    telemetry, violation = print_payloads()
    client = HttpIngestClient(
        base_url=str(cfg.get("http_ingest_base_url", "")),
        api_key=str(cfg.get("http_ingest_api_key", "")),
        timeout_sec=float(cfg.get("http_timeout_sec", 10.0)),
        enabled=bool(cfg.get("http_enabled", True)),
    )

    if not client.enabled:
        print("\nHTTP ingest is disabled or missing FW_INGEST_API_KEY.")
        print("Set FW_INGEST_API_KEY and rerun to validate the live backend.")
        return

    telemetry_result = client.post_telemetry(telemetry)
    violation_result = client.post_violation(violation)

    print("\nBackend results")
    print("=" * 60)
    print(f"Telemetry: ok={telemetry_result.ok} status={telemetry_result.status_code} body={telemetry_result.body}")
    print(f"Violation: ok={violation_result.ok} status={violation_result.status_code} body={violation_result.body}")


def run_aws_test(cfg: dict) -> None:
    telemetry, violation = print_payloads()

    if not PAHO_AVAILABLE:
        print("\npaho-mqtt is not installed. Run: pip install paho-mqtt")
        return

    cert_dir = Path(str(cfg["cert_dir"]))
    ca_path = cert_dir / str(cfg["ca_cert"])
    cert_path = cert_dir / str(cfg["device_cert"])
    key_path = cert_dir / str(cfg["private_key"])
    missing = [path.name for path in (ca_path, cert_path, key_path) if not path.exists()]
    if missing:
        print("\nAWS IoT certificates are missing.")
        print(f"Expected under {cert_dir}: {', '.join(missing)}")
        return

    topic_prefix = str(cfg["mqtt_topic_prefix"]).strip("/")
    site_id = str(cfg.get("site_id", "SITE-001"))
    camera_id = "FP_CAM_001"
    topic_root = f"{topic_prefix}/{site_id}/{camera_id}"
    telemetry_topic = f"{topic_root}/{cfg['mqtt_telemetry_topic']}"
    violation_topic = f"{topic_root}/{cfg['mqtt_violation_topic']}"

    connected = {"value": False}
    client = mqtt.Client(client_id=f"fw-local-test-{int(time.time())}")

    def on_connect(_client, _userdata, _flags, rc):
        connected["value"] = rc == 0
        print(f"\nMQTT connect rc={rc}")

    client.on_connect = on_connect
    client.tls_set(ca_certs=str(ca_path), certfile=str(cert_path), keyfile=str(key_path))
    client.connect(str(cfg["broker_host"]), int(cfg["broker_port"]), int(cfg["keep_alive"]))
    client.loop_start()

    deadline = time.time() + 10.0
    while time.time() < deadline and not connected["value"]:
        time.sleep(0.25)

    if not connected["value"]:
        print("Could not establish AWS IoT connection within 10 seconds.")
        client.loop_stop()
        client.disconnect()
        return

    telemetry_result = client.publish(telemetry_topic, json.dumps(telemetry), qos=0)
    violation_result = client.publish(violation_topic, json.dumps(violation), qos=1)
    time.sleep(1.0)
    client.loop_stop()
    client.disconnect()

    print("\nAWS IoT publish results")
    print("=" * 60)
    print(f"Telemetry topic: {telemetry_topic} rc={telemetry_result.rc}")
    print(f"Violation topic: {violation_topic} rc={violation_result.rc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="edge_ros2 local cloud smoke test")
    parser.add_argument("--mode", choices=["mock", "backend", "aws"], default="mock")
    args = parser.parse_args()

    cfg = load_config()
    print(f"Mode: {args.mode}")

    if args.mode == "mock":
        print_payloads()
    elif args.mode == "backend":
        run_backend_test(cfg)
    else:
        run_aws_test(cfg)


if __name__ == "__main__":
    main()
