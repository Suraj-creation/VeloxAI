from __future__ import annotations

from services.query_api.repositories.edge_runtime_repo import EdgeRuntimeRepository


def handle_get_edge_runtime_status(repo: EdgeRuntimeRepository) -> dict:
    return repo.get_runtime_status()
