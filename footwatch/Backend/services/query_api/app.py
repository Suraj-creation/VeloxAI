from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from services.common.errors import ApiError
from services.common.response import ok
from services.query_api.handlers.get_edge_config import handle_get_edge_config
from services.query_api.handlers.get_edge_runtime_status import handle_get_edge_runtime_status
from services.query_api.handlers.get_alerts import handle_get_alerts
from services.query_api.handlers.get_evidence_url import handle_get_evidence_url
from services.query_api.handlers.get_live_cameras import handle_get_live_cameras
from services.query_api.handlers.get_violation_details import handle_get_violation_details
from services.query_api.handlers.get_violations_summary import handle_get_violations_summary
from services.query_api.handlers.list_violations import handle_list_violations
from services.query_api.handlers.put_edge_config import handle_put_edge_config
from services.query_api.repositories.alerts_read_repo import AlertsReadRepository
from services.query_api.repositories.edge_runtime_repo import EdgeRuntimeRepository
from services.query_api.repositories.evidence_repo import EvidenceRepository
from services.query_api.repositories.live_state_read_repo import LiveStateReadRepository
from services.query_api.repositories.violations_read_repo import ViolationsReadRepository

app = FastAPI(title="FootWatch Query API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

live_repo = LiveStateReadRepository()
violations_repo = ViolationsReadRepository()
evidence_repo = EvidenceRepository()
alerts_repo = AlertsReadRepository()
edge_repo = EdgeRuntimeRepository()


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    request_id = str(uuid.uuid4())
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict(request_id=request_id))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/live/cameras")
def get_live_cameras():
    request_id = str(uuid.uuid4())
    return ok(handle_get_live_cameras(live_repo), request_id)


@app.get("/v1/violations")
def list_violations(
    limit: int = Query(default=50, ge=1, le=200),
    camera_id: Optional[str] = Query(default=None),
    plate: Optional[str] = Query(default=None),
    vehicle_class: Optional[str] = Query(default=None, alias="class"),
    status: Optional[str] = Query(default=None),
    from_ts: Optional[str] = Query(default=None, alias="from"),
    to_ts: Optional[str] = Query(default=None, alias="to"),
):
    request_id = str(uuid.uuid4())
    filters = {
        key: value
        for key, value in {
            "camera_id": camera_id,
            "plate": plate,
            "class": vehicle_class,
            "status": status,
            "from": from_ts,
            "to": to_ts,
        }.items()
        if value is not None and value != ""
    }
    return ok(handle_list_violations(violations_repo, limit=limit, filters=filters), request_id)


@app.get("/v1/violations/summary")
def get_violations_summary():
    request_id = str(uuid.uuid4())
    return ok(handle_get_violations_summary(violations_repo), request_id)


@app.get("/v1/alerts")
def list_alerts(limit: int = Query(default=20, ge=1, le=100)):
    request_id = str(uuid.uuid4())
    return ok(handle_get_alerts(alerts_repo, limit=limit), request_id)


@app.get("/v1/violations/{violation_id}")
def get_violation_details(violation_id: str):
    request_id = str(uuid.uuid4())
    return ok(handle_get_violation_details(violations_repo, violation_id), request_id)


@app.get("/v1/violations/{violation_id}/evidence-url")
def get_evidence_url(violation_id: str, type: str = Query(default="full_frame")):
    request_id = str(uuid.uuid4())
    return ok(handle_get_evidence_url(evidence_repo, violations_repo, violation_id, type), request_id)


@app.get("/v1/edge/live-preview")
def get_edge_live_preview():
    request_id = str(uuid.uuid4())
    return ok(handle_get_edge_runtime_status(edge_repo), request_id)


@app.get("/v1/edge/live-preview/frame")
def get_edge_live_preview_frame():
    frame_bytes = edge_repo.get_preview_frame_bytes()
    if frame_bytes is None:
        raise ApiError(status_code=404, code="edge_preview_not_found", message="Edge preview frame not available")

    return Response(
        content=frame_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/v1/edge/config")
def get_edge_config():
    request_id = str(uuid.uuid4())
    return ok(handle_get_edge_config(edge_repo), request_id)


@app.put("/v1/edge/config")
def put_edge_config(payload: Dict[str, Any] = Body(default_factory=dict)):
    request_id = str(uuid.uuid4())
    return ok(handle_put_edge_config(edge_repo, payload), request_id)
