from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.responses import Response
from httpx import ASGITransport, AsyncClient

from app.core.errors import install_error_handlers
from app.core.middleware import RequestContextMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/plain")
    async def plain() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/pdf")
    async def pdf() -> Response:
        return Response(
            b"%PDF-",
            media_type="application/pdf",
            headers={"Content-Security-Policy": "sandbox", "Cache-Control": "no-store"},
        )

    @app.get("/public")
    async def public() -> Response:
        return Response(b"{}", headers={"Cache-Control": "public, max-age=3600"})

    return app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://api") as client:
        yield client


async def test_default_security_headers(client: AsyncClient) -> None:
    headers = (await client.get("/plain")).headers

    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert "camera=()" in headers["permissions-policy"]
    assert headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in headers


async def test_route_headers_win_over_defaults(client: AsyncClient) -> None:
    pdf = (await client.get("/pdf")).headers
    public = (await client.get("/public")).headers

    assert pdf["content-security-policy"] == "sandbox"
    assert public["cache-control"] == "public, max-age=3600"


async def test_hsts_only_over_https() -> None:
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="https://api") as client:
        headers = (await client.get("/plain")).headers

    assert headers["strict-transport-security"].startswith("max-age=")


async def test_error_responses_carry_headers_too(client: AsyncClient) -> None:
    headers = (await client.get("/missing")).headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-request-id"].startswith("req_")
