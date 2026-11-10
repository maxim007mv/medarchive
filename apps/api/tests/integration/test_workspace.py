import re
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from api_stack import (
    ACCESS_KEY_PATTERN,
    Api,
    create_archive,
    csrf,
    redis_container,
    running_api,
    settings_for,
    write_kek,
)
from conftest import DatabaseUrls
from httpx import AsyncClient, Response

from app.core.ratelimit import WORKSPACE_DELETE, cookie_subject
from app.db.engine import create_engine
from app.modules.auth import service as auth_service
from app.modules.auth.access_key import AccessKey, generate_access_key, parse_access_key
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


async def _rotate(client: AsyncClient, created: Response, key: str | None = None) -> Response:
    return await client.post(
        "/api/v1/workspace/access-key",
        headers={**csrf(created), "Idempotency-Key": key or secrets.token_hex(16)},
    )


async def _login(api: Api, access_key: str) -> int:
    async with api.client() as device:
        response = await device.post("/api/v1/sessions", json={"access_key": access_key})
    return response.status_code


async def test_summary_of_new_archive(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        response = await client.get("/api/v1/workspace")

    body = response.json()
    assert response.status_code == 200
    assert body["id"] == created.json()["workspace"]["id"]
    assert (body["document_count"], body["total_bytes"], body["undated_count"]) == (0, 0, 0)
    assert body["consent"]["policy_version"] == "2026-11-10"
    assert response.headers["etag"].startswith('"w')
    assert response.headers["cache-control"] == "no-store"


async def test_tc083_rotation_revokes_previous_key(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        old_key = created.json()["access_key"]
        response = await _rotate(client, created)

    body = response.json()
    assert response.status_code == 201
    assert body["revoked_previous"] is True
    assert body["access_key"] != old_key
    assert re.fullmatch(ACCESS_KEY_PATTERN, body["access_key"])
    assert await _login(api, old_key) == 401
    assert await _login(api, body["access_key"]) == 201


async def test_rotation_repeat_returns_same_key(api: Api) -> None:
    key = secrets.token_hex(16)
    async with api.client() as client:
        created = await create_archive(client)
        first = await _rotate(client, created, key)
        repeat = await _rotate(client, created, key)

    assert repeat.status_code == 201
    assert repeat.json() == first.json()
    assert repeat.headers["idempotent-replayed"] == "true"
    assert await _login(api, first.json()["access_key"]) == 201


async def test_rotation_retries_a_lookup_id_that_is_taken(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with api.client() as owner, api.client() as other:
        first = await create_archive(owner)
        created = await create_archive(other)
        taken = parse_access_key(first.json()["access_key"])
        assert taken is not None
        fresh = generate_access_key()
        draws = iter([AccessKey(taken.lookup_id, fresh.secret), fresh])
        monkeypatch.setattr(auth_service, "generate_access_key", lambda: next(draws))
        response = await _rotate(other, created)

    assert response.status_code == 201
    assert response.json()["access_key"] == fresh.display
    assert await _login(api, fresh.display) == 201
    assert await _login(api, first.json()["access_key"]) == 201


async def test_rotation_needs_idempotency_key_and_csrf(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        no_key = await client.post("/api/v1/workspace/access-key", headers=csrf(created))
        no_csrf = await client.post(
            "/api/v1/workspace/access-key", headers={"Idempotency-Key": secrets.token_hex(16)}
        )

    assert (no_key.status_code, no_key.json()["code"]) == (400, "idempotency_key_missing")
    assert (no_csrf.status_code, no_csrf.json()["code"]) == (403, "csrf_failed")


async def test_tc084_delete_archive_closes_session_and_key(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        etag = (await client.get("/api/v1/workspace")).headers["etag"]
        response = await client.request(
            "DELETE", "/api/v1/workspace", headers={**csrf(created), "If-Match": etag}
        )
        client.cookies.set("__Host-ma_sid", created.cookies["__Host-ma_sid"])
        session = await client.get("/api/v1/session")

    body = response.json()
    assert response.status_code == 202
    assert body["status"] == "scheduled"
    purge_before = datetime.fromisoformat(body["purge_before"])
    assert timedelta(hours=23) < purge_before - datetime.now(UTC) <= timedelta(hours=24)
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert session.status_code == 401
    assert await _login(api, created.json()["access_key"]) == 401


async def test_delete_without_if_match_is_precondition_required(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        response = await client.request("DELETE", "/api/v1/workspace", headers=csrf(created))
        still_there = await client.get("/api/v1/workspace")

    assert response.status_code == 428
    assert response.json()["code"] == "precondition_required"
    assert still_there.status_code == 200


async def test_delete_with_stale_etag_is_version_conflict(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        current = (await client.get("/api/v1/workspace")).headers["etag"]
        response = await client.request(
            "DELETE", "/api/v1/workspace", headers={**csrf(created), "If-Match": '"w0"'}
        )

    assert response.status_code == 412
    assert response.json()["code"] == "version_conflict"
    assert response.json()["etag"] == current


def _delete_budget(response: Response) -> str:
    assert response.headers["ratelimit-policy"] == '"workspace_delete";q=1;w=3600'
    return response.headers["ratelimit"]


async def test_rejected_deletes_do_not_spend_the_hourly_budget(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        etag = (await client.get("/api/v1/workspace")).headers["etag"]
        without_csrf = await client.request(
            "DELETE", "/api/v1/workspace", headers={"If-Match": etag}
        )
        without_if_match = await client.request(
            "DELETE", "/api/v1/workspace", headers=csrf(created)
        )
        stale = await client.request(
            "DELETE", "/api/v1/workspace", headers={**csrf(created), "If-Match": '"w0"'}
        )
        accepted = await client.request(
            "DELETE", "/api/v1/workspace", headers={**csrf(created), "If-Match": etag}
        )
        client.cookies.set("__Host-ma_sid", created.cookies["__Host-ma_sid"])
        after = await client.request(
            "DELETE", "/api/v1/workspace", headers={**csrf(created), "If-Match": etag}
        )

    statuses = [r.status_code for r in (without_csrf, without_if_match, stale, accepted, after)]
    assert statuses == [403, 428, 412, 202, 401]
    for rejected in (without_csrf, without_if_match, stale):
        assert _delete_budget(rejected) == '"workspace_delete";r=1;t=0'
    assert _delete_budget(accepted) == '"workspace_delete";r=0;t=3600'
    assert _delete_budget(after).startswith('"workspace_delete";r=0;')


async def test_delete_over_budget_is_429_and_keeps_the_archive(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        etag = (await client.get("/api/v1/workspace")).headers["etag"]
        subject = cookie_subject(created.cookies["__Host-ma_sid"])
        await api.app.state.rate_limiter.hit(WORKSPACE_DELETE, subject)
        response = await client.request(
            "DELETE", "/api/v1/workspace", headers={**csrf(created), "If-Match": etag}
        )
        still_there = await client.get("/api/v1/workspace")

    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert 3500 <= int(response.headers["retry-after"]) <= 3600
    assert _delete_budget(response).startswith('"workspace_delete";r=0;')
    assert still_there.status_code == 200


async def test_document_types_are_cacheable_reference_data(api: Api) -> None:
    async with api.client() as client:
        await create_archive(client)
        response = await client.get("/api/v1/document-types")
        again = await client.get("/api/v1/document-types")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"code": "analysis", "title": "Анализ"},
            {"code": "conclusion", "title": "Заключение"},
            {"code": "other", "title": "Другое"},
        ]
    }
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.headers["etag"] == again.headers["etag"]


async def test_readyz_when_everything_is_up(api: Api) -> None:
    async with api.client() as client:
        response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["checks"] == {"db": "ok", "storage": "ok", "kek": "ok"}


async def test_readyz_is_503_when_any_dependency_is_down(api: Api, tmp_path: Path) -> None:
    unreachable_db = create_engine("postgresql+asyncpg://nobody:x@127.0.0.1:9/none")
    api.app.state.db_engine = unreachable_db
    api.app.state.settings = api.app.state.settings.model_copy(
        update={"kek_keyset_path": tmp_path / "missing.json"}
    )
    api.app.state.storage = ObjectStorage(
        endpoint="http://127.0.0.1:9",
        public_endpoint="http://127.0.0.1:9",
        access_key="x",
        secret_key="y",  # noqa: S106  # unreachable endpoint, nothing is sent
        quarantine_bucket="ma-quarantine",
        docs_bucket="ma-docs",
    )
    async with api.client() as client:
        response = await client.get("/readyz")

    await unreachable_db.dispose()
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"db": "unavailable", "storage": "unavailable", "kek": "unavailable"},
    }
