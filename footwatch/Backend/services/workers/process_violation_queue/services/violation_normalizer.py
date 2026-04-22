from __future__ import annotations

from datetime import datetime, timezone

from services.common.config import load_settings


def normalize_violation(payload: dict) -> dict:
    settings = load_settings()
    now = datetime.now(timezone.utc).isoformat()
    confidence = float(payload.get("vehicle", {}).get("plate_ocr_confidence", 0.0))
    evidence = payload.get("evidence", {})
    has_evidence = isinstance(evidence, dict) and any(
        isinstance(value, str) and value.strip() for value in evidence.values()
    )

    review_required = confidence < 0.65
    status = "REQUIRES_REVIEW" if review_required else "CONFIRMED_AUTO"

    return {
        **payload,
        "violation_type": payload.get("violation_type", "FOOTPATH_ENCROACHMENT"),
        "fine_amount_inr": payload.get("fine_amount_inr", settings.challan_fine_amount_inr),
        "violation_status": status,
        "review_required": review_required,
        "review_reason": "low_ocr_confidence" if review_required else None,
        "evidence_status": payload.get("evidence_status", "READY" if has_evidence else "PENDING_UPLOAD"),
        "created_at": now,
        "updated_at": now,
    }
