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
    project_root: Path

    @property
    def local_data_dir(self) -> Path:
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
        project_root=root,
    )
