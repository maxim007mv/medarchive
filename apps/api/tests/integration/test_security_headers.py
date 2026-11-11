"""TC-094 for the auth and workspace routes: no caching of personal data, API CSP, no sniffing."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from api_stack import (
    Api,
    create_archive,
    redis_container,
    running_api,
    settings_for,
    write_kek,
)
from conftest import DatabaseUrls
from httpx import ASGITransport, AsyncClient, Headers

from app.storage.s3 import ObjectStorage

API_CSP = "default-src 'none'; frame-ancestors 'none'"


@pytest.fixture(scope="module")
def redis_url() -> Iterator[str]:
    yield from redis_container()


@pytest.fixture
async def api(
    database: DatabaseUrls, storage: ObjectStorage, redis_url: str, tmp_path: Path
) -> AsyncIterator[Api]:
    settings = settings_for(database.app, redis_url, write_kek(tmp_path / "kek.json"))
    async with running_api(settings, storage) as api:
        yield api


def assert_api_headers(headers: Headers) -> None:
    assert headers["content-security-policy"] == API_CSP
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert "geolocation=()" in headers["permissions-policy"]
    assert headers["x-request-id"]


async def test_tc094_personal_data_answers_are_not_stored(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        answers = [
            created,
            await client.get("/api/v1/session"),
            await client.get("/api/v1/workspace"),
            await client.post(
                "/api/v1/sessions", json={"access_key": created.json()["access_key"]}
            ),
        ]
    async with api.client() as anonymous:
        answers.append(await anonymous.get("/api/v1/workspace"))

    for response in answers:
        assert response.headers["cache-control"] == "no-store", response.url
        assert_api_headers(response.headers)


async def test_hsts_only_over_https(api: Api) -> None:
    async with api.client() as client:
        secure = await client.get("/healthz")
    transport = ASGITransport(app=api.app, client=("10.9.9.9", 1))
    async with AsyncClient(transport=transport, base_url="http://api.test") as client:
        plain = await client.get("/healthz")

    assert secure.headers["strict-transport-security"].startswith("max-age=")
    assert "strict-transport-security" not in plain.headers
    assert_api_headers(plain.headers)
