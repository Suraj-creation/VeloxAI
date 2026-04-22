from __future__ import annotations

from pathlib import Path

from services.common.errors import ApiError
from services.query_api.repositories.violations_read_repo import ViolationsReadRepository


def handle_get_challan_download(repo: ViolationsReadRepository, violation_id: str) -> Path:
    violation = repo.by_id(violation_id)
    if not violation:
        raise ApiError(404, "not_found", "Violation not found")

    challan = violation.get("challan", {})
    pdf_path = challan.get("pdf_path")
    if not isinstance(pdf_path, str) or not pdf_path:
        raise ApiError(404, "challan_not_ready", "Challan PDF not available yet")

    path = Path(pdf_path)
    if not path.exists():
        raise ApiError(404, "challan_not_found", "Stored challan PDF could not be found")

    return path
