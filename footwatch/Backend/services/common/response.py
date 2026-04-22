from __future__ import annotations


def ok(data: dict, request_id: str) -> dict:
    return {
        "request_id": request_id,
        "data": data,
    }


def created(data: dict, request_id: str) -> dict:
    return {
        "request_id": request_id,
        "data": data,
    }
