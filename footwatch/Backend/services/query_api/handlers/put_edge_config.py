from __future__ import annotations

from services.query_api.repositories.edge_runtime_repo import EdgeRuntimeRepository


def handle_put_edge_config(repo: EdgeRuntimeRepository, payload: dict) -> dict:
    return repo.update_config(payload)
