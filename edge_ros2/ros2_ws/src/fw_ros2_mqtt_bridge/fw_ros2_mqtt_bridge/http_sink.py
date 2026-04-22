from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class HttpDeliveryResult:
    ok: bool
    status_code: int
    body: str
    retryable: bool


class HttpIngestClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_sec: float = 10.0,
        enabled: bool = True,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_sec = timeout_sec
        self.enabled = enabled and bool(self.base_url) and bool(self.api_key)
        self._session = session or requests.Session()

    def post_telemetry(self, payload: dict[str, Any]) -> HttpDeliveryResult:
        return self._post("/v1/telemetry", payload)

    def post_violation(self, payload: dict[str, Any]) -> HttpDeliveryResult:
        violation_id = str(payload.get("violation_id", "")).strip()
        headers = {"x-idempotency-key": violation_id} if violation_id else None
        return self._post("/v1/violations", payload, extra_headers=headers)

    def deliver(self, target: str, payload: dict[str, Any]) -> HttpDeliveryResult:
        clean_target = "/" + str(target).lstrip("/")
        return self._post(clean_target, payload)

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        extra_headers: dict[str, str] | None = None,
    ) -> HttpDeliveryResult:
        if not self.enabled:
            return HttpDeliveryResult(
                ok=False,
                status_code=0,
                body="HTTP ingest disabled",
                retryable=False,
            )

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }
        if extra_headers:
            headers.update(extra_headers)

        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            response = self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout_sec,
            )
        except requests.RequestException as exc:
            return HttpDeliveryResult(
                ok=False,
                status_code=0,
                body=str(exc),
                retryable=True,
            )

        ok = 200 <= response.status_code < 300
        retryable = response.status_code in {408, 409, 425, 429} or response.status_code >= 500
        return HttpDeliveryResult(
            ok=ok,
            status_code=int(response.status_code),
            body=response.text[:400],
            retryable=retryable,
        )
