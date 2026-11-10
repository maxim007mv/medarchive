"""BE-12 over real Redis: headers on every answer of limited routes, quotas, atomicity."""

import asyncio
import secrets
from collections.abc import AsyncIterator, Iterator
from ipaddress import ip_network
from pathlib import Path

import pytest
from api_stack import (
    CONSENT,
    Api,
    create_archive,
    redis_container,
    running_api,
    settings_for,
    write_kek,
)
from conftest import DatabaseUrls
from redis.asyncio import Redis

from app.core.ratelimit import RateLimiter, RatePolicy, Subject
from app.storage.s3 import ObjectStorage


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


@pytest.mark.parametrize("path", ["/api/v1/session", "/api/v1/workspace", "/api/v1/document-types"])
async def test_general_limit_headers_also_on_401(api: Api, path: str) -> None:
    async with api.client() as client:
        anonymous = await client.get(path)
        await create_archive(client)
        first = await client.get(path)
        second = await client.get(path)

    assert anonymous.status_code == 401
    for response in (anonymous, first, second):
        assert response.headers["ratelimit-policy"] == '"general";q=300;w=60'
    assert anonymous.headers["ratelimit"] == '"general";r=300;t=0'
    remaining = [int(r.headers["ratelimit"].split("r=")[1].split(";")[0]) for r in (first, second)]
    assert remaining[1] == remaining[0] - 1


async def test_requests_without_session_do_not_spend_session_budgets(api: Api) -> None:
    async with api.client() as client:
        anonymous = [await client.request("DELETE", "/api/v1/workspace") for _ in range(3)]

    assert [response.status_code for response in anonymous] == [401, 401, 401]


async def test_health_routes_are_not_limited(api: Api) -> None:
    async with api.client() as client:
        responses = [await client.get(path) for path in ("/healthz", "/readyz", "/metrics")]

    for response in responses:
        assert "ratelimit" not in response.headers
        assert "ratelimit-policy" not in response.headers


async def test_archive_creation_is_limited_to_ten_per_hour_per_address(api: Api) -> None:
    async with api.client() as client:
        for _ in range(10):
            await create_archive(client)
        eleventh = await client.post(
            "/api/v1/workspaces", json=CONSENT, headers={"Idempotency-Key": secrets.token_hex(16)}
        )

    assert eleventh.status_code == 429
    assert eleventh.headers["ratelimit-policy"] == '"workspaces";q=10;w=3600'
    assert 1 <= int(eleventh.headers["retry-after"]) <= 360


async def test_login_limit_counts_the_forwarded_client_behind_a_trusted_proxy(
    database: DatabaseUrls, storage: ObjectStorage, redis_url: str, tmp_path: Path
) -> None:
    # D-005: every browser reaches the API from the address of the Next.js container.
    settings = settings_for(database.app, redis_url, write_kek(tmp_path / "kek.json"))
    behind_proxy = settings.model_copy(update={"trusted_proxies": [ip_network("10.0.0.0/8")]})
    async with running_api(behind_proxy, storage) as api, api.client(ip="10.1.1.1") as proxy:
        for _ in range(6):
            await proxy.post(
                "/api/v1/sessions",
                json={"access_key": "Z" * 24},
                headers={"X-Forwarded-For": "203.0.113.7"},
            )
        other_person = await proxy.post(
            "/api/v1/sessions",
            json={"access_key": "Z" * 24},
            headers={"X-Forwarded-For": "198.51.100.4"},
        )
        spoofed = await proxy.post(
            "/api/v1/sessions",
            json={"access_key": "Z" * 24},
            headers={"X-Forwarded-For": "198.51.100.9, 203.0.113.7"},
        )

    assert other_person.status_code == 401
    assert spoofed.status_code == 429


async def test_limits_can_be_switched_off_for_gate_runs(
    database: DatabaseUrls, storage: ObjectStorage, redis_url: str, tmp_path: Path
) -> None:
    # D-006: functional E2E and k6 runs create many archives from one address.
    settings = settings_for(database.app, redis_url, write_kek(tmp_path / "kek.json"))
    unlimited = settings.model_copy(update={"rate_limits_enabled": False})
    async with running_api(unlimited, storage) as api, api.client() as client:
        attempts = [
            await client.post("/api/v1/sessions", json={"access_key": "Z" * 24}) for _ in range(7)
        ]

    assert [response.status_code for response in attempts] == [401] * 7
    assert attempts[-1].headers["ratelimit"] == '"login";r=5;t=0'


async def test_concurrent_hits_never_exceed_the_quota(redis_url: str) -> None:
    redis = Redis.from_url(redis_url)
    limiter = RateLimiter(redis)
    policy = RatePolicy(f"burst_{secrets.token_hex(4)}", 5, 60, Subject.IP)

    decisions = await asyncio.gather(*(limiter.hit(policy, "ip:10.0.0.1") for _ in range(20)))
    await redis.aclose()

    assert sum(decision.allowed for decision in decisions) == 5
