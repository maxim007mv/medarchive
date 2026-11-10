import json
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import install_error_handlers
from app.core.middleware import RequestContextMiddleware
from app.core.observability import SCRUBBED, configure_logging, scrub_event

TITLE = "Заключение онколога"


def test_sentry_event_keeps_only_location_of_failure() -> None:
    event: dict[str, Any] = {
        "request": {
            "method": "PATCH",
            "url": "https://medarchive.local/api/v1/documents/1?q=онколог",
            "data": {"title": TITLE},
            "cookies": {"__Host-ma_sid": "token"},
            "headers": {"X-CSRF-Token": "csrf"},
            "query_string": "q=онколог",
        },
        "exception": {
            "values": [
                {
                    "type": "IntegrityError",
                    "value": f"duplicate key ({TITLE})",
                    "stacktrace": {"frames": [{"function": "update", "vars": {"title": TITLE}}]},
                }
            ]
        },
        "user": {"ip_address": "10.0.0.1"},
        "extra": {"title": TITLE},
        "breadcrumbs": {"values": [{"message": TITLE}]},
    }

    scrubbed = json.dumps(scrub_event(event, None), ensure_ascii=False)

    assert TITLE not in scrubbed
    assert "онколог" not in scrubbed
    assert "token" not in scrubbed
    assert "csrf" not in scrubbed
    assert "10.0.0.1" not in scrubbed
    assert SCRUBBED in scrubbed
    assert '"function": "update"' in scrubbed
    assert "https://medarchive.local/api/v1/documents/1" in scrubbed


async def test_access_log_has_route_template_not_query_or_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/api/v1/documents/{document_id}")
    async def document(document_id: str, q: str = "") -> dict[str, str]:
        return {"title": TITLE}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api") as client:
        await client.get("/api/v1/documents/abc", params={"q": "онколог"})

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    request_line = next(line for line in lines if line["event"] == "request")
    assert request_line["route"] == "/api/v1/documents/{document_id}"
    assert request_line["status"] == 200
    assert request_line["request_id"].startswith("req_")
    assert "онколог" not in json.dumps(lines, ensure_ascii=False)
    assert TITLE not in json.dumps(lines, ensure_ascii=False)
