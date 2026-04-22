from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class EvidenceRepository:
    def build_signed_url(self, violation_id: str, evidence_type: str, violation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        if violation:
            evidence = violation.get("evidence", {})
            evidence_path = evidence.get(evidence_type)
            if isinstance(evidence_path, str) and evidence_path:
                path = Path(evidence_path)
                if path.exists():
                    return {
                        "url": path.resolve().as_uri(),
                        "expires_at": expires_at.isoformat(),
                    }

        return {
            "url": f"https://example.invalid/evidence/{violation_id}/{evidence_type}",
            "expires_at": expires_at.isoformat(),
        }
