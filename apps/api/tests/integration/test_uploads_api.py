import io
import secrets
from uuid import uuid4

import pytest
from api_stack import Api, create_archive
from documents_support import (
    SOURCES,
    create_document,
    generated,
    request_upload,
    upload,
    write_headers,
)
from pypdf import PdfReader, PdfWriter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.storage.s3 import ObjectStorage
from app.workers.purge import Purger

MAX_BYTES = 20_971_520


async def test_upload_returns_presigned_post_for_exact_key(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        response = await request_upload(client, created, name="01.pdf", size_bytes=79114)

    body = response.json()
    assert response.status_code == 201
    workspace_id = created.json()["workspace"]["id"]
    assert body["fields"]["key"] == f"q/{workspace_id}/{body['upload_id']}.bin"
    assert body["fields"]["Content-Type"] == "application/pdf"
    assert body["max_bytes"] == MAX_BYTES
    assert response.headers["cache-control"] == "no-store"


async def test_tc016_big_file_is_413_before_any_storage_request(
    api: Api, storage: ObjectStorage
) -> None:
    big = generated("big-21mb.pdf")
    async with api.client() as client:
        created = await create_archive(client)
        response = await request_upload(
            client, created, name=big.name, size_bytes=big.stat().st_size
        )

    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"
    workspace_id = created.json()["workspace"]["id"]
    assert list(storage.quarantine.list(f"q/{workspace_id}/")) == []


async def test_upload_of_another_content_type_is_not_pdf(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        response = await client.post(
            "/api/v1/uploads",
            headers=write_headers(created),
            json={"original_name": "a.png", "size_bytes": 67, "content_type": "image/png"},
        )

    assert response.status_code == 415
    assert response.json()["code"] == "not_pdf"


async def test_upload_create_is_idempotent(api: Api) -> None:
    body = {"original_name": "01.pdf", "size_bytes": 79114, "content_type": "application/pdf"}
    async with api.client() as client:
        created = await create_archive(client)
        headers = write_headers(created)
        first = await client.post("/api/v1/uploads", headers=headers, json=body)
        second = await client.post("/api/v1/uploads", headers=headers, json=body)

    assert second.status_code == 201
    assert second.headers["idempotent-replayed"] == "true"
    assert second.json() == first.json()


@pytest.mark.parametrize(
    ("fixture", "status", "code"),
    [
        pytest.param("fake.pdf", 415, "not_pdf", id="TC-015"),
        pytest.param("encrypted.pdf", 422, "pdf_encrypted", id="TC-017"),
        pytest.param("broken.pdf", 422, "pdf_unreadable", id="TC-018"),
    ],
)
async def test_rejected_files(
    api: Api, storage: ObjectStorage, fixture: str, status: int, code: str
) -> None:
    path = generated(fixture)
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(client, created, path.read_bytes(), path.name)
        response = await create_document(client, created, upload_id, title="Документ")
        again = await create_document(client, created, upload_id, title="Документ")
        listed = await client.get("/api/v1/documents")

    assert (response.status_code, response.json()["code"]) == (status, code)
    assert again.json()["code"] == code
    assert listed.json()["total"] == 0
    workspace_id = created.json()["workspace"]["id"]
    assert list(storage.docs.list(f"ws/{workspace_id}/")) == []


async def test_upload_incomplete_without_object(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        response = await request_upload(client, created, name="01.pdf", size_bytes=79114)
        result = await create_document(client, created, response.json()["upload_id"])

    assert result.status_code == 409
    assert result.json()["code"] == "upload_incomplete"


async def test_unknown_upload_is_not_found(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        response = await create_document(client, created, str(uuid4()))

    assert response.status_code == 404
    assert response.json()["code"] == "upload_not_found"


async def test_upload_of_another_archive_is_not_found(api: Api) -> None:
    source = SOURCES[0]
    async with api.client() as owner, api.client() as stranger:
        created = await create_archive(owner)
        upload_id = await upload(owner, created, source.path.read_bytes(), source.path.name)
        response = await create_document(stranger, await create_archive(stranger), upload_id)

    assert response.status_code == 404
    assert response.json()["code"] == "upload_not_found"


async def _expire(superuser: AsyncEngine, upload_id: str, hours_ago: int) -> None:
    async with superuser.begin() as connection:
        await connection.execute(
            text(
                "UPDATE app.uploads SET created_at = now() - make_interval(hours => :hours + 1),"
                " expires_at = now() - make_interval(hours => :hours) WHERE id = :id"
            ),
            {"id": upload_id, "hours": hours_ago},
        )


async def test_upload_past_its_hour_stays_410_for_a_day_after_purge(
    api: Api,
    superuser_engine: AsyncEngine,
    worker_sessions: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
) -> None:
    source = SOURCES[0]
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(client, created, source.path.read_bytes(), source.path.name)
        await _expire(superuser_engine, upload_id, hours_ago=2)
        await Purger(worker_sessions, storage).run_once()
        response = await create_document(client, created, upload_id)

    assert response.status_code == 410
    assert response.json()["code"] == "upload_expired"
    key = f"q/{created.json()['workspace']['id']}/{upload_id}.bin"
    assert storage.quarantine.size(key) == source.size_bytes


async def test_upload_a_day_past_expiry_is_purged_with_its_object(
    api: Api,
    superuser_engine: AsyncEngine,
    worker_sessions: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
) -> None:
    source = SOURCES[0]
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(client, created, source.path.read_bytes(), source.path.name)
        await _expire(superuser_engine, upload_id, hours_ago=25)
        await Purger(worker_sessions, storage).run_once()
        response = await create_document(client, created, upload_id)

    assert response.status_code == 404
    assert response.json()["code"] == "upload_not_found"
    key = f"q/{created.json()['workspace']['id']}/{upload_id}.bin"
    assert storage.quarantine.size(key) is None


async def test_consumed_upload_cannot_make_a_second_document(api: Api) -> None:
    source = SOURCES[0]
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(client, created, source.path.read_bytes(), source.path.name)
        first = await create_document(client, created, upload_id)
        second = await create_document(client, created, upload_id, key=secrets.token_hex(16))

    assert first.status_code == 201
    assert second.status_code == 404
    assert second.json()["code"] == "upload_not_found"


def _owner_password_only(source: bytes) -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(source)))
    writer.encrypt(user_password="", owner_password=secrets.token_hex(8), algorithm="AES-256")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


async def test_owner_password_only_pdf_is_stored(api: Api) -> None:
    data = _owner_password_only(SOURCES[0].path.read_bytes())
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(client, created, data, "lab-report.pdf")
        response = await create_document(client, created, upload_id, title="Выписка")
        content = await client.get(f"/api/v1/documents/{response.json()['id']}/content")

    assert response.status_code == 201, response.text
    assert response.json()["file"]["page_count"] == 1
    assert content.content == data
