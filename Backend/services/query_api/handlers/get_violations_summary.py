from __future__ import annotations

from services.query_api.repositories.violations_read_repo import ViolationsReadRepository


def handle_get_violations_summary(repo: ViolationsReadRepository) -> dict:
    return repo.summary()
