from __future__ import annotations

from services.common.errors import ApiError
from services.query_api.repositories.evidence_repo import EvidenceRepository
from services.query_api.repositories.violations_read_repo import ViolationsReadRepository


def handle_get_evidence_url(
    repo: EvidenceRepository,
    violations_repo: ViolationsReadRepository,
    violation_id: str,
    evidence_type: str,
) -> dict:
    violation = violations_repo.by_id(violation_id)
    if not violation:
        raise ApiError(404, "not_found", "Violation not found")
    return repo.build_signed_url(violation_id=violation_id, evidence_type=evidence_type, violation=violation)
