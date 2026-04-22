from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from services.common.local_violation_store import deep_merge_dict, LocalViolationStore
from services.ingest_api.repositories.evidence_event_repo import EvidenceEventRepository
from services.workers.process_violation_queue.services.challan_engine import ChallanEngine


def handle_post_evidence_complete(violation_id: str, payload: Dict[str, Any]) -> dict:
    evidence_repo = EvidenceEventRepository()
    violation_store = LocalViolationStore()
    challan_engine = ChallanEngine()

    enriched = evidence_repo.record(violation_id, payload)
    violation = violation_store.get(violation_id)

    challan_status = "PENDING_VIOLATION"
    if violation:
        merged = deep_merge_dict(
            violation,
            {
                "evidence_status": payload.get("evidence_status", "READY"),
                "evidence": payload.get("evidence", {}),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        merged["challan"] = challan_engine.build_for_violation(
            merged,
            existing_challan=merged.get("challan"),
        )
        violation_store.upsert(merged)
        challan_status = str(merged["challan"].get("status", "UNKNOWN"))

    return {
        "violation_id": violation_id,
        "recorded": True,
        "challan_status": challan_status,
        "evidence_recorded_at": enriched["timestamp"],
    }
