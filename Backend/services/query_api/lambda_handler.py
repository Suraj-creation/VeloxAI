from __future__ import annotations

from mangum import Mangum

from services.query_api.app import app

handler = Mangum(app)
