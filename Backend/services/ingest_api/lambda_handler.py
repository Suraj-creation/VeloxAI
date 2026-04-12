from __future__ import annotations

from mangum import Mangum

from services.ingest_api.app import app

handler = Mangum(app)
