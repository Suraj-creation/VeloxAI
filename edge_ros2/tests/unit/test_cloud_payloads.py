from __future__ import annotations

import os
import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[2] / "ros2_ws" / "src"
sys.path.insert(0, str(SRC / "fw_ros2_mqtt_bridge"))

from fw_ros2_mqtt_bridge.payloads import resolve_runtime_config


def test_resolve_runtime_config_uses_relative_cert_dir(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    certs_dir = tmp_path / "certs"
    config_dir.mkdir()
    certs_dir.mkdir()

    raw = {
        "cert_dir": "../certs",
        "http_ingest_base_url": "https://example.com/ingest",
        "http_api_key_env": "FW_INGEST_API_KEY",
    }
    monkeypatch.setenv("FW_INGEST_API_KEY", "secret-key")

    resolved = resolve_runtime_config(config_dir, raw)

    assert resolved["cert_dir"] == str(certs_dir.resolve())
    assert resolved["http_ingest_api_key"] == "secret-key"
    assert resolved["http_ingest_base_url"] == "https://example.com/ingest"
