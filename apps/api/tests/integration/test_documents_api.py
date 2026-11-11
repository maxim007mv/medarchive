import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import pytest
from api_stack import CONSENT, Api, create_archive
from documents_support import (
    SOURCES,
    add_source,
    create_document,
    generated,
    upload,
    write_headers,
)
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

GENERAL_BLOOD_TEST = SOURCES[0]
MSK = ZoneInfo("Europe/Moscow")


async def _with_document(client: AsyncClient) -> tuple[Response, dict[str, Any]]:
    created = await create_archive(client)
    return created, await add_source(client, created, GENERAL_BLOOD_TEST)


async def test_tc010_create_returns_document_with_etag_and_location(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(
            client, created, GENERAL_BLOOD_TEST.path.read_bytes(), GENERAL_BLOOD_TEST.path.name
        )
        response = await create_document(
            client,
            created,
            upload_id,
            title="  Общий анализ крови ",
            type="analysis",
            document_date="2026-04-08",
            note="",
        )

    body = response.json()
    assert response.status_code == 201
    assert response.headers["etag"] == '"v1"'
    assert response.headers["location"] == f"/api/v1/documents/{body['id']}"
    assert body["title"] == "Общий анализ крови"
    assert body["note"] is None
    assert body["version"] == 1
    assert body["file"] == {
        "original_name": GENERAL_BLOOD_TEST.path.name,
        "size_bytes": GENERAL_BLOOD_TEST.size_bytes,
        "page_count": 1,
    }


async def test_tc019_repeated_key_replays_one_document(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(
            client, created, GENERAL_BLOOD_TEST.path.read_bytes(), GENERAL_BLOOD_TEST.path.name
        )
        key = "0b8e1d3a-6d0e-4f53-9a43-2f1c7e5a9d10"
        first = await create_document(client, created, upload_id, key=key, title="Анализ")
        second = await create_document(client, created, upload_id, key=key, title="Анализ")
        listed = await client.get("/api/v1/documents")

    assert second.status_code == 201
    assert second.headers["idempotent-replayed"] == "true"
    assert second.json() == first.json()
    assert second.headers["etag"] == first.headers["etag"]
    assert listed.json()["total"] == 1


async def test_tc022_create_without_idempotency_key(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        headers = write_headers(created)
        del headers["Idempotency-Key"]
        response = await client.post(
            "/api/v1/documents",
            headers=headers,
            json={
                "upload_id": "01930c70-1f2a-7d3b-8c4d-5e6f7a8b9c0d",
                "title": "А",
                "type": "other",
            },
        )

    assert response.status_code == 400
    assert response.json()["code"] == "idempotency_key_missing"


async def test_tc023_same_key_other_title_is_reused(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(
            client, created, GENERAL_BLOOD_TEST.path.read_bytes(), GENERAL_BLOOD_TEST.path.name
        )
        key = "9b1f4c1e-5a0e-4a65-9a0b-6a2d1f0c3e11"
        await create_document(client, created, upload_id, key=key, title="Первое")
        response = await create_document(client, created, upload_id, key=key, title="Второе")

    assert response.status_code == 422
    assert response.json()["code"] == "idempotency_key_reused"


async def test_tc014_date_in_future_by_user_zone(api: Api) -> None:
    tomorrow = (datetime.now(MSK) + timedelta(days=1)).date().isoformat()
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(
            client, created, GENERAL_BLOOD_TEST.path.read_bytes(), GENERAL_BLOOD_TEST.path.name
        )
        response = await create_document(client, created, upload_id, document_date=tomorrow)

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "date_in_future"
    assert body["errors"] == [
        {
            "pointer": "/document_date",
            "code": "date_in_future",
            "title": "Дата документа не может быть позже сегодняшней",
        }
    ]


async def test_tc024_cyrillic_file_name_is_kept(api: Api) -> None:
    path = generated("cyrillic «имя» файла.pdf")
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(client, created, path.read_bytes(), path.name)
        document = await create_document(
            client, created, upload_id, title="Общий анализ крови", document_date="2026-04-08"
        )
        content = await client.get(
            f"/api/v1/documents/{document.json()['id']}/content",
            params={"disposition": "attachment"},
        )

    assert document.json()["file"]["original_name"] == "cyrillic «имя» файла.pdf"
    disposition = content.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="2026-04-08_obshchiy-analiz-krovi.pdf"')
    assert unquote(disposition.split("filename*=UTF-8''")[1]) == (
        "2026-04-08_Общий анализ крови.pdf"
    )


async def test_tc050_card_with_etag_and_304(api: Api) -> None:
    async with api.client() as client:
        _, document = await _with_document(client)
        card = await client.get(f"/api/v1/documents/{document['id']}")
        cached = await client.get(
            f"/api/v1/documents/{document['id']}", headers={"If-None-Match": '"v1"'}
        )

    assert card.status_code == 200
    assert card.json() == document
    assert card.headers["etag"] == '"v1"'
    assert card.headers["cache-control"] == "no-store"
    assert cached.status_code == 304
    assert cached.content == b""


async def test_tc090_document_of_another_archive_is_404(api: Api) -> None:
    async with api.client() as owner, api.client() as stranger:
        _, document = await _with_document(owner)
        await create_archive(stranger)
        card = await stranger.get(f"/api/v1/documents/{document['id']}")
        content = await stranger.get(f"/api/v1/documents/{document['id']}/content")

    assert (card.status_code, card.json()["code"]) == (404, "not_found")
    assert (content.status_code, content.json()["code"]) == (404, "not_found")


async def test_malformed_id_is_404(api: Api) -> None:
    async with api.client() as client:
        await create_archive(client)
        response = await client.get("/api/v1/documents/not-a-uuid")

    assert response.status_code == 404


async def test_tc057_tc094_content_is_byte_identical_with_safe_headers(api: Api) -> None:
    async with api.client() as client:
        _, document = await _with_document(client)
        response = await client.get(f"/api/v1/documents/{document['id']}/content")

    assert response.status_code == 200
    assert hashlib.sha256(response.content).hexdigest() == GENERAL_BLOOD_TEST.sha256
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-length"] == str(GENERAL_BLOOD_TEST.size_bytes)
    assert response.headers["content-security-policy"] == "sandbox"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-disposition"].startswith(
        'inline; filename="2026-04-08_obshchiy-analiz-krovi.pdf"'
    )


async def test_range_request_is_206(api: Api) -> None:
    source = GENERAL_BLOOD_TEST.path.read_bytes()
    async with api.client() as client:
        _, document = await _with_document(client)
        response = await client.get(
            f"/api/v1/documents/{document['id']}/content", headers={"Range": "bytes=0-65535"}
        )

    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes 0-65535/{len(source)}"
    assert response.headers["content-length"] == "65536"
    assert response.content == source[:65536]


async def test_tc096_title_is_ciphertext_and_not_logged(
    api: Api, superuser_engine: AsyncEngine, capfd: pytest.CaptureFixture[str]
) -> None:
    title = "Заключение онколога"
    async with api.client() as client:
        created = await create_archive(client)
        upload_id = await upload(
            client, created, GENERAL_BLOOD_TEST.path.read_bytes(), GENERAL_BLOOD_TEST.path.name
        )
        document = (await create_document(client, created, upload_id, title=title)).json()
        await client.get("/api/v1/documents", params={"q": "онколог"})
        await client.get(f"/api/v1/documents/{document['id']}")
    async with superuser_engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT d.title_ct, f.original_name_ct FROM app.documents d"
                    " JOIN app.document_files f ON f.document_id = d.id WHERE d.id = :id"
                ),
                {"id": document["id"]},
            )
        ).one()

    assert title.encode() not in row.title_ct
    assert GENERAL_BLOOD_TEST.path.name.encode() not in row.original_name_ct
    logs = capfd.readouterr()
    for secret in (title, "онколог", GENERAL_BLOOD_TEST.path.name):
        assert secret not in logs.out + logs.err


async def test_tc058_patch_without_if_match_is_428(api: Api) -> None:
    async with api.client() as client:
        created, document = await _with_document(client)
        response = await client.patch(
            f"/api/v1/documents/{document['id']}",
            headers=write_headers(created),
            json={"note": "x"},
        )

    assert response.status_code == 428
    assert response.json()["code"] == "precondition_required"


async def test_tc059_patch_with_stale_etag_is_412_with_current(api: Api) -> None:
    async with api.client() as client:
        created, document = await _with_document(client)
        url = f"/api/v1/documents/{document['id']}"
        first = await client.patch(
            url, headers={**write_headers(created), "If-Match": '"v1"'}, json={"note": "раз"}
        )
        stale = await client.patch(
            url, headers={**write_headers(created), "If-Match": '"v1"'}, json={"note": "два"}
        )

    assert first.status_code == 200
    assert first.headers["etag"] == '"v2"'
    assert stale.status_code == 412
    assert stale.json()["code"] == "version_conflict"
    assert stale.json()["etag"] == '"v2"'


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"workspace_id": "01930c6e-7b1a-7c2e-9f4e-3a5d2b1c0e9f"}, id="TC-097-ws"),
        pytest.param({"version": 5}, id="TC-097-version"),
        pytest.param({"uploaded_at": "2026-01-01T00:00:00Z"}, id="uploaded-at-immutable"),
        pytest.param({}, id="empty-body"),
    ],
)
async def test_tc097_patch_rejects_extra_fields(api: Api, body: dict[str, Any]) -> None:
    async with api.client() as client:
        created, document = await _with_document(client)
        response = await client.patch(
            f"/api/v1/documents/{document['id']}",
            headers={**write_headers(created), "If-Match": '"v1"'},
            json=body,
        )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_patch_changes_fields_and_reindexes_title(api: Api) -> None:
    async with api.client() as client:
        created, document = await _with_document(client)
        url = f"/api/v1/documents/{document['id']}"
        patched = await client.patch(
            url,
            headers={**write_headers(created), "If-Match": '"v1"'},
            json={"title": "Липидограмма", "type": "other", "document_date": None, "note": "  "},
        )
        old_title = await client.get("/api/v1/documents", params={"q": "анализ"})
        new_title = await client.get("/api/v1/documents", params={"q": "липид"})
        card = await client.get(url)

    body = patched.json()
    assert patched.status_code == 200
    assert (body["title"], body["type"], body["document_date"], body["note"]) == (
        "Липидограмма",
        "other",
        None,
        None,
    )
    assert body["version"] == 2
    assert body["uploaded_at"] == document["uploaded_at"]
    assert old_title.json()["matched"] == 0
    assert new_title.json()["matched"] == 1
    assert card.json() == body


async def test_tc099_audit_of_patch_names_fields_without_values(
    api: Api, superuser_engine: AsyncEngine
) -> None:
    old_note, new_title, new_note = "Натощак", "Липидограмма", "Повторить через месяц"
    async with api.client() as client:
        created, document = await _with_document(client)
        url = f"/api/v1/documents/{document['id']}"
        noted = await client.patch(
            url, headers={**write_headers(created), "If-Match": '"v1"'}, json={"note": old_note}
        )
        patched = await client.patch(
            url,
            headers={**write_headers(created), "If-Match": '"v2"'},
            json={"title": new_title, "note": new_note},
        )
    async with superuser_engine.connect() as connection:
        row = (
            await connection.execute(
                text("SELECT * FROM app.audit_log WHERE entity_id = :id ORDER BY id DESC LIMIT 1"),
                {"id": document["id"]},
            )
        ).one()

    assert (noted.status_code, patched.status_code) == (200, 200)
    assert row.action == "document.update"
    assert row.changed_fields == ["title", "note"]
    values = [str(value) for value in row]
    for secret in (GENERAL_BLOOD_TEST.title, old_note, new_title, new_note):
        assert not any(secret in value for value in values)


async def test_delete_is_soft_and_repeat_is_404(api: Api) -> None:
    async with api.client() as client:
        created, document = await _with_document(client)
        url = f"/api/v1/documents/{document['id']}"
        stale = await client.delete(url, headers={**write_headers(created), "If-Match": '"v9"'})
        missing = await client.delete(url, headers=write_headers(created))
        deleted = await client.delete(url, headers={**write_headers(created), "If-Match": '"v1"'})
        again = await client.delete(url, headers={**write_headers(created), "If-Match": '"v1"'})
        card = await client.get(url)
        listed = await client.get("/api/v1/documents")

    assert stale.status_code == 412
    assert missing.status_code == 428
    assert deleted.status_code == 204
    assert again.status_code == 404
    assert card.status_code == 404
    assert listed.json()["total"] == 0


@pytest.mark.parametrize(
    ("timezone", "status"),
    [
        pytest.param("Pacific/Kiritimati", 201, id="ahead"),
        pytest.param("Pacific/Pago_Pago", 422, id="behind"),
    ],
)
async def test_today_is_the_day_of_the_archive_zone(api: Api, timezone: str, status: int) -> None:
    # Kiritimati (UTC+14) is always at least a day ahead of Pago Pago (UTC-11).
    kiritimati_today = datetime.now(ZoneInfo("Pacific/Kiritimati")).date().isoformat()
    async with api.client() as client:
        created = await client.post(
            "/api/v1/workspaces",
            json={**CONSENT, "timezone": timezone},
            headers={"Idempotency-Key": secrets.token_hex(16)},
        )
        upload_id = await upload(
            client, created, GENERAL_BLOOD_TEST.path.read_bytes(), GENERAL_BLOOD_TEST.path.name
        )
        response = await create_document(client, created, upload_id, document_date=kiritimati_today)

    assert response.status_code == status, response.text
