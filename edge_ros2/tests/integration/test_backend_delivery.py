from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


SRC = Path(__file__).resolve().parents[2] / "ros2_ws" / "src"
sys.path.insert(0, str(SRC / "fw_ros2_mqtt_bridge"))

from fw_ros2_mqtt_bridge.http_sink import HttpIngestClient


class CaptureHandler(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        CaptureHandler.calls.append(
            {
                "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()},
                "body": json.loads(body or "{}"),
            }
        )
        self.send_response(201 if self.path.endswith("/violations") else 200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, format, *args):  # noqa: A003
        return


def test_http_ingest_client_posts_backend_contract_payloads():
    server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    CaptureHandler.calls.clear()

    try:
        base_url = f"http://127.0.0.1:{server.server_port}/ingest"
        client = HttpIngestClient(
            base_url=base_url,
            api_key="demo-key",
            timeout_sec=2.0,
            enabled=True,
        )

        telemetry_result = client.post_telemetry(
            {
                "device_id": "pi-001",
                "camera_id": "FP_CAM_001",
                "timestamp": "2026-04-23T10:00:00+00:00",
                "fps": 12.5,
                "latency_ms": 55.0,
                "status": "active",
            }
        )
        violation_result = client.post_violation(
            {
                "violation_id": "vio-001",
                "timestamp": "2026-04-23T10:00:01+00:00",
                "location": {"camera_id": "FP_CAM_001"},
                "vehicle": {
                    "plate_number": "KA05AB1234",
                    "plate_ocr_confidence": 0.91,
                    "vehicle_class": "motorcycle",
                    "estimated_speed_kmph": 21.0,
                },
            }
        )

        assert telemetry_result.ok
        assert violation_result.ok
        assert len(CaptureHandler.calls) == 2
        assert CaptureHandler.calls[0]["path"] == "/ingest/v1/telemetry"
        assert CaptureHandler.calls[1]["path"] == "/ingest/v1/violations"
        assert CaptureHandler.calls[1]["headers"]["x-idempotency-key"] == "vio-001"
    finally:
        server.shutdown()
        server.server_close()
