import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

class EdgeSyncClient:
    """Client for syncing edge telemetry and violations to the cloud backend."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = "dev-key"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": self.api_key})

    def send_telemetry(self, camera_id: str, fps: float, latency_ms: float, frame_failures: int = 0) -> bool:
        """Send camera health telemetry to the ingest API."""
        url = f"{self.base_url}/v1/telemetry"
        payload = {
            "camera_id": camera_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "online",
            "fps": fps,
            "latency_ms": latency_ms,
            "reconnects": 0,
            "frame_failures": frame_failures
        }
        try:
            resp = self.session.post(url, json=payload, timeout=5)
            resp.raise_for_status()
            logger.debug(f"Telemetry synced for {camera_id}")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to sync telemetry: {e}")
            return False

    def send_violation(self, violation_data: dict) -> Optional[str]:
        """Send violation metadata to the ingest API."""
        url = f"{self.base_url}/v1/violations"
        # Generate idempotency key if not present
        idempotency_key = str(uuid.uuid4())
        headers = {"x-idempotency-key": idempotency_key}
        
        try:
            resp = self.session.post(url, json=violation_data, headers=headers, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            if isinstance(result, dict) and "data" in result:
                # Based on common response wrapper
               return result.get("data", {}).get("violation_id", violation_data.get("violation_id"))
            return violation_data.get("violation_id")
        except requests.RequestException as e:
            logger.error(f"Failed to sync violation: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def upload_evidence(self, violation_id: str, frame_bytes: bytes, plate_bytes: bytes = None) -> bool:
        """Upload evidence. In a real system, this requests a signed URL from backend,
        or we complete evidence processing directly.
        """
        # For simplicity in this demo, we simulate completing the evidence
        url = f"{self.base_url}/v1/violations/{violation_id}/evidence-complete"
        payload = {
            "evidence_keys": ["full_frame.jpg", "plate_crop.jpg"]
        }
        try:
            resp = self.session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"Evidence completed for violation {violation_id}")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to complete evidence for {violation_id}: {e}")
            return False

if __name__ == "__main__":
    # Test script
    logging.basicConfig(level=logging.INFO)
    client = EdgeSyncClient()
    client.send_telemetry("cam-001", fps=15.2, latency_ms=120)
