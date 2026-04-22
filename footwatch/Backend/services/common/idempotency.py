from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def payload_hash(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
