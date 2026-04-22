from __future__ import annotations

import json

from services.common.local_violation_store import LocalViolationStore


class ViolationPersister:
    def __init__(self) -> None:
        self._store = LocalViolationStore()

    def persist(self, payload: dict) -> None:
        self._store.upsert(json.loads(json.dumps(payload)))
