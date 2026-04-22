from __future__ import annotations

from services.query_api.repositories.alerts_read_repo import AlertsReadRepository


def handle_get_alerts(repo: AlertsReadRepository, limit: int = 20) -> dict:
    return {
        "items": repo.list_all(limit=limit),
    }
