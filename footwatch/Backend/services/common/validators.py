from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import ValidationError, validate

from services.common.errors import ApiError


def load_schema(schema_name: str) -> Dict[str, Any]:
    schema_path = Path(__file__).resolve().parents[1] / "contracts" / "schemas" / schema_name
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_payload(payload: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    try:
        validate(instance=payload, schema=schema)
    except ValidationError as exc:
        raise ApiError(400, "invalid_payload", f"Payload schema validation failed: {exc.message}") from exc
