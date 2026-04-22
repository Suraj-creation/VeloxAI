from __future__ import annotations

from services.common.errors import ApiError
from services.query_api.repositories.violations_read_repo import ViolationsReadRepository


def handle_get_violation_details(repo: ViolationsReadRepository, violation_id: str) -> dict:
    violation = repo.by_id(violation_id)
    if not violation:
        raise ApiError(404, "not_found", "Violation not found")
    return violation
