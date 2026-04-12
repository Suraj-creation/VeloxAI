from __future__ import annotations

from services.query_api.repositories.live_state_read_repo import LiveStateReadRepository


def handle_get_live_cameras(repo: LiveStateReadRepository) -> dict:
    return {
        "items": repo.list_all(),
    }
