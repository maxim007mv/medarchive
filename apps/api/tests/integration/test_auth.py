import re
import secrets
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
from api_stack import (
    ACCESS_KEY_PATTERN,
    CONSENT,
    Api,
    create_archive,
    csrf,
    redis_container,
    running_api,
    settings_for,
    write_kek,
)
from conftest import DatabaseUrls

from app.storage.s3 import ObjectStorage

SCOPES = ["documents:read", "documents:write", "exports:create", "workspace:manage"]


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


def _without_request_id(body: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in body.items() if name != "request_id"}


async def test_tc002_create_archive_sets_host_session_cookie(api: Api) -> None:
    async with api.client() as client:
        response = await create_archive(client)

    body = response.json()
    cookie = response.headers["set-cookie"]
    assert re.match(r"__Host-ma_sid=[A-Za-z0-9_-]{43};", cookie)
    attributes = {part.strip().lower() for part in cookie.split(";")[1:]}
    assert {"httponly", "secure", "path=/", "samesite=lax"} <= attributes
    max_age = next(int(part.split("=")[1]) for part in attributes if part.startswith("max-age="))
    assert 2_591_990 <= max_age <= 2_592_000
    assert "domain" not in cookie.lower()
    assert re.fullmatch(ACCESS_KEY_PATTERN, body["access_key"])
    assert body["scopes"] == SCOPES
    assert body["workspace"]["document_count"] == 0
    assert body["workspace"]["created_at"].endswith("Z")
    assert response.headers["cache-control"] == "no-store"


async def test_tc003_consent_not_accepted_is_rejected_without_cookie(api: Api) -> None:
    async with api.client() as client:
        response = await client.post(
            "/api/v1/workspaces",
            json={"consent": {"policy_version": "2026-11-10", "accepted": False}},
            headers={"Idempotency-Key": secrets.token_hex(16)},
        )

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "validation_error"
    assert body["errors"][0]["pointer"] == "/consent/accepted"
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(
    ("payload", "pointer"),
    [
        ({}, "/consent"),
        (
            {"consent": {"policy_version": "2025-01-01", "accepted": True}},
            "/consent/policy_version",
        ),
        ({**CONSENT, "timezone": "Mars/Olympus"}, "/timezone"),
        ({**CONSENT, "workspace_id": "x"}, "/workspace_id"),
    ],
)
async def test_invalid_creation_bodies(api: Api, payload: dict[str, Any], pointer: str) -> None:
    async with api.client() as client:
        response = await client.post(
            "/api/v1/workspaces", json=payload, headers={"Idempotency-Key": secrets.token_hex(16)}
        )

    assert response.status_code == 422
    assert [error["pointer"] for error in response.json()["errors"]] == [pointer]


async def test_creation_requires_idempotency_key(api: Api) -> None:
    async with api.client() as client:
        response = await client.post("/api/v1/workspaces", json=CONSENT)

    assert response.status_code == 400
    assert response.json()["code"] == "idempotency_key_missing"


async def test_repeated_creation_returns_same_archive_with_new_session(api: Api) -> None:
    key = secrets.token_hex(16)
    async with api.client() as first_device, api.client() as second_device:
        first = await create_archive(first_device, key)
        repeat = await create_archive(second_device, key)

    assert repeat.headers["idempotent-replayed"] == "true"
    assert "idempotent-replayed" not in first.headers
    assert repeat.json()["workspace"] == first.json()["workspace"]
    assert repeat.json()["access_key"] == first.json()["access_key"]
    assert repeat.json()["csrf_token"] != first.json()["csrf_token"]
    assert repeat.cookies["__Host-ma_sid"] != first.cookies["__Host-ma_sid"]


async def test_creation_key_with_other_body_is_reused_error(api: Api) -> None:
    key = secrets.token_hex(16)
    async with api.client() as client:
        await create_archive(client, key)
        response = await client.post(
            "/api/v1/workspaces",
            json={**CONSENT, "timezone": "Asia/Yekaterinburg"},
            headers={"Idempotency-Key": key},
        )

    assert response.status_code == 422
    assert response.json()["code"] == "idempotency_key_reused"


async def test_session_returns_csrf_and_scopes(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        response = await client.get("/api/v1/session")

    body = response.json()
    assert response.status_code == 200
    assert body["workspace_id"] == created.json()["workspace"]["id"]
    assert body["csrf_token"] == created.json()["csrf_token"]
    assert body["scopes"] == SCOPES
    assert body["idle_expires_at"].endswith("Z")
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("cookie", [None, "garbage", "A" * 43])
async def test_session_without_valid_cookie_is_unauthenticated(
    api: Api, cookie: str | None
) -> None:
    async with api.client() as client:
        if cookie:
            client.cookies.set("__Host-ma_sid", cookie)
        response = await client.get("/api/v1/session")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"
    assert response.json()["title"] == "Сессия закончилась. Откройте архив ключом доступа"


@pytest.mark.parametrize("token", [None, "", "forged"])
async def test_tc093_state_change_without_csrf_token_fails(api: Api, token: str | None) -> None:
    async with api.client() as client:
        await create_archive(client)
        headers = {} if token is None else {"X-CSRF-Token": token}
        response = await client.delete("/api/v1/sessions/current", headers=headers)
        still_signed_in = await client.get("/api/v1/session")

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
    assert still_signed_in.status_code == 200


async def test_csrf_token_of_another_session_fails(api: Api) -> None:
    async with api.client() as first, api.client() as second:
        other = await create_archive(first)
        await create_archive(second)
        response = await second.delete("/api/v1/sessions/current", headers=csrf(other))

    assert response.status_code == 403


async def test_logout_revokes_session_and_clears_cookie(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        cookie = client.cookies["__Host-ma_sid"]
        response = await client.delete("/api/v1/sessions/current", headers=csrf(created))
        client.cookies.set("__Host-ma_sid", cookie)
        after = await client.get("/api/v1/session")

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert after.status_code == 401


@pytest.mark.parametrize(
    "transform",
    [lambda key: key, lambda key: key.replace("-", "").lower()],
    ids=["as-shown", "typed"],
)
async def test_access_key_opens_archive_on_another_device(api: Api, transform: Any) -> None:
    async with api.client() as owner, api.client() as other_device:
        created = await create_archive(owner)
        response = await other_device.post(
            "/api/v1/sessions", json={"access_key": transform(created.json()["access_key"])}
        )
        session = await other_device.get("/api/v1/session")

    assert response.status_code == 201
    assert response.json()["workspace_id"] == created.json()["workspace"]["id"]
    assert response.json()["scopes"] == SCOPES
    assert "__Host-ma_sid=" in response.headers["set-cookie"]
    assert session.json()["csrf_token"] == response.json()["csrf_token"]


async def test_tc082_five_wrong_keys_then_rate_limited(api: Api) -> None:
    async with api.client() as owner:
        real_key = (await create_archive(owner)).json()["access_key"]
    wrong_secret = real_key[:-1] + ("0" if real_key[-1] != "0" else "1")
    unknown_archive = "ZZZZ-ZZ" + real_key[7:]
    attempts = [wrong_secret, unknown_archive, wrong_secret, unknown_archive, "Z" * 24]

    async with api.client() as attacker:
        failures = [
            await attacker.post("/api/v1/sessions", json={"access_key": key}) for key in attempts
        ]
        sixth = await attacker.post("/api/v1/sessions", json={"access_key": real_key})

    assert [response.status_code for response in failures] == [401] * 5
    bodies = [_without_request_id(response.json()) for response in failures]
    assert all(body == bodies[0] for body in bodies)
    assert bodies[0]["code"] == "access_key_invalid"
    assert bodies[0]["title"] == "Ключ не подошёл. Проверьте символы"
    assert sixth.status_code == 429
    assert sixth.json()["code"] == "rate_limited"
    assert 1 <= int(sixth.headers["retry-after"]) <= 180
    assert sixth.headers["ratelimit-policy"] == '"login";q=5;w=900'
    assert sixth.headers["ratelimit"].startswith('"login";r=0;')


async def test_login_limit_is_per_address(api: Api) -> None:
    async with api.client() as owner:
        real_key = (await create_archive(owner)).json()["access_key"]
    async with api.client(ip="10.200.0.1") as attacker:
        for _ in range(6):
            await attacker.post("/api/v1/sessions", json={"access_key": "Z" * 24})
    async with api.client(ip="10.200.0.2") as person:
        response = await person.post("/api/v1/sessions", json={"access_key": real_key})

    assert response.status_code == 201
