from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIOLATIONS_DIR = PROJECT_ROOT / "violations"
CONFIG_DIR = PROJECT_ROOT / "config"
METRICS_FILE = PROJECT_ROOT / ".metrics.json"
STATE_FILE = PROJECT_ROOT / ".backend_sync_state.json"
INGEST_CFG_FILE = CONFIG_DIR / "backend_ingest.json"


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
        return fallback
    except Exception:
        return fallback


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def post_json(
    base_url: str,
    route: str,
    payload: dict[str, Any],
    api_key: str,
    idempotency_key: str | None = None,
    timeout_sec: float = 8.0,
) -> tuple[int, dict[str, Any] | None]:
    url = base_url.rstrip("/") + route
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
    }
    if idempotency_key:
        headers["x-idempotency-key"] = idempotency_key

    req = urllib.request.Request(url, method="POST", headers=headers)
    body = json.dumps(payload).encode("utf-8")

    try:
        with urllib.request.urlopen(req, data=body, timeout=timeout_sec) as response:
            data = response.read().decode("utf-8")
            return response.status, json.loads(data) if data else None
    except urllib.error.HTTPError as exc:
        data = exc.read().decode("utf-8")
        parsed: dict[str, Any] | None = None
        if data:
            try:
                parsed = json.loads(data)
            except Exception:
                parsed = {"raw": data}
        return exc.code, parsed


def list_violation_records() -> list[dict[str, Any]]:
    if not VIOLATIONS_DIR.exists():
        return []

    records: list[dict[str, Any]] = []
    for candidate in sorted(VIOLATIONS_DIR.iterdir()):
        if not candidate.is_dir():
            continue
        metadata_file = candidate / "violation_metadata.json"
        if not metadata_file.exists():
            continue

        metadata = load_json(metadata_file, {})
        if not metadata:
            continue
        if not metadata.get("violation_id"):
            continue

        records.append(metadata)

    records.sort(key=lambda item: str(item.get("timestamp", "")))
    return records


def build_telemetry_payload(metrics: dict[str, Any], camera_cfg: dict[str, Any]) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    stats = metrics.get("stats", {}) if isinstance(metrics.get("stats"), dict) else {}
    session = metrics.get("session", {}) if isinstance(metrics.get("session"), dict) else {}

    running = bool(metrics.get("running"))
    status = "online" if running else "stale"

    timestamp = metrics.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp:
        timestamp = now_iso

    return {
        "camera_id": str(camera_cfg.get("camera_id", "FP_CAM_001")),
        "timestamp": timestamp,
        "fps": float(metrics.get("inference_fps", 0.0) or 0.0),
        "latency_ms": float(metrics.get("elapsed_ms", 0.0) or 0.0),
        "reconnects": int(session.get("reconnects", 0) or 0),
        "frame_failures": int(session.get("frame_failures", 0) or 0),
        "status": status,
        "location_name": str(camera_cfg.get("location_name", "Unknown")),
    }


def sync_once(base_url: str, api_key: str, telemetry: bool, state: dict[str, Any]) -> dict[str, Any]:
    camera_cfg = load_json(
        CONFIG_DIR / "footpath_roi.json",
        {
            "camera_id": "FP_CAM_001",
            "location_name": "Unknown",
        },
    )
    metrics = load_json(METRICS_FILE, {})

    pushed_ids = set(state.get("pushed_violation_ids", []))

    if telemetry:
        payload = build_telemetry_payload(metrics, camera_cfg)
        code, _ = post_json(base_url, "/v1/telemetry", payload, api_key)
        print(f"telemetry -> status={code}")

    pushed_count = 0
    records = list_violation_records()
    for record in records:
        violation_id = str(record.get("violation_id"))
        if violation_id in pushed_ids:
            continue

        idem_key = f"edge-{violation_id}"
        code, body = post_json(base_url, "/v1/violations", record, api_key, idempotency_key=idem_key)
        print(f"violation {violation_id} -> status={code}")
        if code >= 300:
            continue

        evidence_payload = {
            "evidence_status": "READY",
            "evidence": record.get("evidence", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        ev_code, _ = post_json(base_url, f"/v1/violations/{violation_id}/evidence-complete", evidence_payload, api_key)
        print(f"evidence complete {violation_id} -> status={ev_code}")

        pushed_ids.add(violation_id)
        pushed_count += 1

    next_state = {
        "pushed_violation_ids": sorted(pushed_ids),
        "last_sync_at": datetime.now(timezone.utc).isoformat(),
    }
    print(f"sync summary -> violations_pushed={pushed_count} total_seen={len(next_state['pushed_violation_ids'])}")
    return next_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push objective_3_footpath outputs to Backend ingest API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Ingest API base URL")
    parser.add_argument("--api-key", default="dev-key", help="Ingest API key")
    parser.add_argument("--interval", type=float, default=2.0, help="Loop interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run one sync cycle and exit")
    parser.add_argument("--skip-telemetry", action="store_true", help="Do not post telemetry payloads")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_json(INGEST_CFG_FILE, {})

    base_url = args.base_url
    if args.base_url == "http://127.0.0.1:8000" and isinstance(cfg.get("ingest_base_url"), str):
        base_url = str(cfg.get("ingest_base_url"))

    api_key = args.api_key
    if args.api_key == "dev-key" and isinstance(cfg.get("api_key"), str):
        api_key = str(cfg.get("api_key"))

    interval = args.interval
    if isinstance(cfg.get("poll_interval_sec"), (int, float)):
        interval = float(cfg.get("poll_interval_sec"))

    state = load_json(STATE_FILE, {"pushed_violation_ids": []})

    while True:
        state = sync_once(
            base_url=base_url,
            api_key=api_key,
            telemetry=not args.skip_telemetry,
            state=state,
        )
        save_json(STATE_FILE, state)

        if args.once:
            break

        time.sleep(max(0.5, interval))


if __name__ == "__main__":
    main()
