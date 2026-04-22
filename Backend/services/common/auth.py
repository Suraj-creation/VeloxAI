from __future__ import annotations

from typing import Optional

from services.common.config import load_settings
from services.common.errors import ApiError


def validate_ingest_api_key(api_key: Optional[str]) -> None:
    expected = load_settings().ingest_api_key
    if not api_key or api_key != expected:
        raise ApiError(401, "unauthorized", "Invalid ingest API key")
