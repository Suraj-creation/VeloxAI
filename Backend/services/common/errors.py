from __future__ import annotations

from typing import Any, Dict, Optional


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def to_dict(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "code": self.code,
            "message": self.message,
        }
        if request_id:
            payload["request_id"] = request_id
        return payload
