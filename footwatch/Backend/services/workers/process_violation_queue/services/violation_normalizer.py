from __future__ import annotations

from datetime import datetime, timezone


def normalize_violation(payload: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    confidence = float(payload.get("vehicle", {}).get("plate_ocr_confidence", 0.0))

    review_required = confidence < 0.65
    status = "REQUIRES_REVIEW" if review_required else "CONFIRMED_AUTO"

    return {
        **payload,
        "violation_status": status,
        "review_required": review_required,
        "review_reason": "low_ocr_confidence" if review_required else None,
        "evidence_status": "READY",
        "created_at": now,
        "updated_at": now,
    }
