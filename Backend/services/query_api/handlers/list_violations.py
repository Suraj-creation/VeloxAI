from __future__ import annotations

from typing import Dict, Optional

from services.query_api.repositories.violations_read_repo import ViolationsReadRepository


def handle_list_violations(
    repo: ViolationsReadRepository,
    limit: int = 50,
    filters: Optional[Dict[str, str]] = None,
) -> dict:
    return {
        "items": repo.list_all(limit=limit, filters=filters),
    }
