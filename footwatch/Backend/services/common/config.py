from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    env: str
    region: str
    camera_state_table: str
    violations_table: str
    idempotency_table: str
    violation_queue_url: str
    evidence_bucket: str
    ingest_api_key: str
    gemini_api_key: str
    gemini_model: str
    challan_fine_amount_inr: int
    challan_pdf_title: str
    project_root: Path

    @property
    def local_data_dir(self) -> Path:
        configured = os.getenv("FW_LOCAL_DATA_DIR")
        if configured:
            directory = Path(configured)
        elif os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            directory = Path("/tmp") / "footwatch" / ".local"
        else:
            directory = self.project_root / ".local"
        directory.mkdir(parents=True, exist_ok=True)
        return directory


def load_settings() -> Settings:
    root = Path(__file__).resolve().parents[2]
    return Settings(
        env=os.getenv("FW_ENV", "dev"),
        region=os.getenv("FW_REGION", "ap-south-1"),
        camera_state_table=os.getenv("FW_CAMERA_STATE_TABLE", "CameraLiveState"),
        violations_table=os.getenv("FW_VIOLATIONS_TABLE", "Violations"),
        idempotency_table=os.getenv("FW_IDEMPOTENCY_TABLE", "IdempotencyRecords"),
        violation_queue_url=os.getenv("FW_VIOLATION_QUEUE_URL", ""),
        evidence_bucket=os.getenv("FW_EVIDENCE_BUCKET", "footwatch-evidence"),
        ingest_api_key=os.getenv("FW_INGEST_API_KEY", "dev-key"),
        gemini_api_key=os.getenv("FW_GEMINI_API_KEY", ""),
        gemini_model=os.getenv("FW_GEMINI_MODEL", "gemini-1.5-flash"),
        challan_fine_amount_inr=int(os.getenv("FW_CHALLAN_FINE_INR", "500")),
        challan_pdf_title=os.getenv("FW_CHALLAN_PDF_TITLE", "TRAFFIC VIOLATION NOTICE"),
        project_root=root,
    )
