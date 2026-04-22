from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from services.common.auth import validate_ingest_api_key
from services.common.errors import ApiError
from services.common.logger import get_logger
from services.common.response import created, ok
from services.ingest_api.handlers.post_evidence_complete import handle_post_evidence_complete
from services.ingest_api.handlers.post_telemetry import handle_post_telemetry
from services.ingest_api.handlers.post_violation import handle_post_violation
from services.ingest_api.repositories.camera_live_state_repo import CameraLiveStateRepository
from services.ingest_api.repositories.idempotency_repo import IdempotencyRepository
from services.ingest_api.repositories.violation_queue_repo import ViolationQueueRepository

logger = get_logger(__name__)
app = FastAPI(title="FootWatch Ingest API", version="0.1.0")

camera_state_repo = CameraLiveStateRepository()
queue_repo = ViolationQueueRepository()
idempotency_repo = IdempotencyRepository()


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    request_id = str(uuid.uuid4())
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict(request_id=request_id))


@app.post("/v1/telemetry")
def post_telemetry(payload: Dict[str, Any], x_api_key: Optional[str] = Header(default=None)):
    validate_ingest_api_key(x_api_key)
    request_id = str(uuid.uuid4())
    logger.info("telemetry_ingest camera_id=%s", payload.get("camera_id"))
    result = handle_post_telemetry(payload, camera_state_repo)
    return ok(result, request_id)


@app.post("/v1/violations", status_code=201)
def post_violation(
    payload: Dict[str, Any],
    x_api_key: Optional[str] = Header(default=None),
    x_idempotency_key: Optional[str] = Header(default=None),
):
    validate_ingest_api_key(x_api_key)
    request_id = str(uuid.uuid4())
    logger.info("violation_ingest violation_id=%s", payload.get("violation_id"))
    result = handle_post_violation(payload, x_idempotency_key, queue_repo, idempotency_repo)
    return created(result, request_id)


@app.post("/v1/violations/{violation_id}/evidence-complete")
def post_evidence_complete(
    violation_id: str,
    payload: Dict[str, Any],
    x_api_key: Optional[str] = Header(default=None),
):
    validate_ingest_api_key(x_api_key)
    request_id = str(uuid.uuid4())
    logger.info("evidence_complete violation_id=%s", violation_id)
    result = handle_post_evidence_complete(violation_id, payload)
    return ok(result, request_id)
