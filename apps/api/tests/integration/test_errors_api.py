"""Every catalog code that auth and workspace routes can produce, as real problem+json answers."""

import hashlib
import secrets
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from api_stack import (
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
from httpx import Response
from sqlalchemy import text

from app.core.crypto import Kek
from app.core.errors import CATALOG, ErrorCode
from app.core.idempotency import request_fingerprint
from app.db.transaction import workspace_tx
from app.modules.auth.schemas import WorkspaceCreate
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


def assert_problem(response: Response, code: ErrorCode) -> None:
    body = response.json()
    assert response.status_code == CATALOG[code].status
    assert response.headers["content-type"] == "application/problem+json"
    assert body["type"] == f"urn:problem-type:medarchive:{code.value}"
    assert body["title"] == CATALOG[code].title
    assert body["code"] == code.value
    assert body["request_id"] == response.headers["x-request-id"]


async def test_validation_error(api: Api) -> None:
    async with api.client() as client:
        response = await client.post(
            "/api/v1/sessions", json={"access_key": "short", "workspace_id": "x"}
        )

    assert_problem(response, ErrorCode.VALIDATION_ERROR)
    assert {error["pointer"] for error in response.json()["errors"]} == {
        "/access_key",
        "/workspace_id",
    }


async def test_unauthenticated_and_access_key_invalid(api: Api) -> None:
    async with api.client() as client:
        assert_problem(await client.get("/api/v1/workspace"), ErrorCode.UNAUTHENTICATED)
        assert_problem(
            await client.post("/api/v1/sessions", json={"access_key": "Z" * 24}),
            ErrorCode.ACCESS_KEY_INVALID,
        )


@pytest.mark.parametrize(
    ("with_csrf", "if_match", "code"),
    [
        (False, "*", ErrorCode.CSRF_FAILED),
        (True, None, ErrorCode.PRECONDITION_REQUIRED),
        (True, '"w0"', ErrorCode.VERSION_CONFLICT),
    ],
)
async def test_archive_deletion_guards(
    api: Api, with_csrf: bool, if_match: str | None, code: ErrorCode
) -> None:
    # Deletion allows one request per hour per session, so each case has its own archive.
    async with api.client() as client:
        created = await create_archive(client)
        headers = csrf(created) if with_csrf else {}
        if if_match:
            headers["If-Match"] = if_match
        response = await client.request("DELETE", "/api/v1/workspace", headers=headers)

    assert_problem(response, code)


async def test_idempotency_codes_of_archive_creation(api: Api, database: DatabaseUrls) -> None:
    key = secrets.token_hex(16)
    async with api.client() as client:
        assert_problem(
            await client.post("/api/v1/workspaces", json=CONSENT), ErrorCode.IDEMPOTENCY_KEY_MISSING
        )
        sessions = api.app.state.db_sessions
        async with sessions() as db, db.begin():
            await db.execute(
                text("SELECT app.claim_workspace_create_key(:key, :fingerprint)"),
                {
                    "key": hashlib.sha256(key.encode()).digest(),
                    "fingerprint": request_fingerprint(WorkspaceCreate.model_validate(CONSENT)),
                },
            )
        in_progress = await client.post(
            "/api/v1/workspaces", json=CONSENT, headers={"Idempotency-Key": key}
        )
        reused = await client.post(
            "/api/v1/workspaces",
            json={**CONSENT, "timezone": "Europe/Samara"},
            headers={"Idempotency-Key": key},
        )

    assert_problem(in_progress, ErrorCode.IDEMPOTENCY_IN_PROGRESS)
    assert in_progress.headers["retry-after"] == "1"
    assert_problem(reused, ErrorCode.IDEMPOTENCY_KEY_REUSED)


async def test_idempotency_in_progress_of_key_rotation(api: Api) -> None:
    key = secrets.token_hex(16)
    async with api.client() as client:
        created = await create_archive(client)
        workspace_id = uuid.UUID(created.json()["workspace"]["id"])
        async with api.app.state.db_sessions() as db, workspace_tx(db, workspace_id):
            await db.execute(
                text(
                    "INSERT INTO app.idempotency_keys (workspace_id, key, operation, fingerprint)"
                    " VALUES (:workspace_id, :key, 'workspace.rotateKey', :fingerprint)"
                ),
                {
                    "workspace_id": workspace_id,
                    "key": key,
                    "fingerprint": request_fingerprint(None),
                },
            )
        response = await client.post(
            "/api/v1/workspace/access-key", headers={**csrf(created), "Idempotency-Key": key}
        )

    assert_problem(response, ErrorCode.IDEMPOTENCY_IN_PROGRESS)


async def test_rate_limited(api: Api) -> None:
    async with api.client() as client:
        for _ in range(5):
            await client.post("/api/v1/sessions", json={"access_key": "Z" * 24})
        response = await client.post("/api/v1/sessions", json={"access_key": "Z" * 24})

    assert_problem(response, ErrorCode.RATE_LIMITED)
    assert int(response.headers["retry-after"]) >= 1


async def test_not_found_for_unknown_route(api: Api) -> None:
    async with api.client() as client:
        assert_problem(await client.get("/api/v1/nothing-here"), ErrorCode.NOT_FOUND)


async def test_internal_without_trace_when_keys_do_not_open(api: Api, tmp_path: Path) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        api.app.state.kek = Kek.from_file(write_kek(tmp_path / "other-kek.json"))
        response = await client.post(
            "/api/v1/workspace/access-key",
            headers={**csrf(created), "Idempotency-Key": secrets.token_hex(16)},
        )

    assert_problem(response, ErrorCode.INTERNAL)
    assert set(response.json()) == {"type", "title", "status", "code", "request_id"}
