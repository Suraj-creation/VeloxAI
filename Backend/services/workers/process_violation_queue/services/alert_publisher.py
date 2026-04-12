from __future__ import annotations

import json
from datetime import datetime, timezone

from services.common.config import load_settings


def publish_alert(violation: dict) -> None:
    settings = load_settings()
    alerts_path = settings.local_data_dir / "alerts.jsonl"

    review_required = violation.get("violation_status") == "REQUIRES_REVIEW"
    severity = "warning" if review_required else "info"

    alert = {
        "alert_id": f"alert_{violation.get('violation_id', 'unknown')}",
        "camera_id": violation.get("location", {}).get("camera_id"),
        "violation_id": violation.get("violation_id"),
        "severity": severity,
        "message": (
            "Violation requires manual review"
            if review_required
            else "Violation processed successfully"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with alerts_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(alert) + "\n")
