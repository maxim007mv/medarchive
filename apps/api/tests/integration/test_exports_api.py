import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from api_stack import Api, create_archive
from documents_support import SOURCES, add_all_sources, write_headers
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

FIXTURE_NAMES = [
    "documents/2026-05-22_uzi-pochek-i-mochevogo-puzyrya.pdf",
    "documents/2026-05-21_lipidogramma.pdf",
    "documents/2026-04-10_zaklyuchenie-terapevta.pdf",
    "documents/2026-04-08_obshchiy-analiz-krovi.pdf",
    "documents/2026-04-08_biokhimicheskiy-analiz-krovi.pdf",
    "documents/bez-daty_ekg-pokoya.pdf",
]


async def _export(client: AsyncClient, created: Response, body: dict[str, Any]) -> Response:
    return await client.post("/api/v1/exports", headers=write_headers(created), json=body)


async def _zip(client: AsyncClient, export: Response) -> tuple[Response, zipfile.ZipFile]:
    response = await client.get(export.json()["content_url"])
    return response, zipfile.ZipFile(io.BytesIO(response.content))


async def test_tc070_whole_archive_zip(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        await add_all_sources(client, created)
        export = await _export(client, created, {"scope": "all"})
        response, archive = await _zip(client, export)

    body = export.json()
    assert export.status_code == 201
    assert body["document_count"] == 6
    assert body["total_bytes"] == sum(source.size_bytes for source in SOURCES)
    assert body["content_url"] == f"/api/v1/exports/{body['id']}/content"
    today = datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat()
    assert response.headers["content-disposition"] == (
        f'attachment; filename="medarchive_{today}.zip"'
    )
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "no-store"
    assert archive.namelist() == [*FIXTURE_NAMES, "documents.csv", "documents.json"]
    by_title = {source.title: source for source in SOURCES}
    rows = list(
        csv.DictReader(
            io.StringIO(archive.read("documents.csv").decode("utf-8-sig")), delimiter=";"
        )
    )
    assert archive.read("documents.csv").startswith(b"\xef\xbb\xbf")
    for row, name in zip(rows, FIXTURE_NAMES, strict=True):
        source = by_title[row["title"]]
        assert row["file_name"] == name.removeprefix("documents/")
        assert row["sha256"] == source.sha256
        assert hashlib.sha256(archive.read(name)).hexdigest() == source.sha256
    assert {row["type"] for row in rows} == {"Анализ", "Заключение"}
    listed = json.loads(archive.read("documents.json"))
    assert [item["file_name"] for item in listed] == [row["file_name"] for row in rows]


async def test_tc071_found_documents_only(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        await add_all_sources(client, created)
        export = await _export(client, created, {"scope": "filtered", "filter": {"q": "анализ"}})
        _, archive = await _zip(client, export)

    assert export.json()["document_count"] == 2
    assert [name for name in archive.namelist() if name.endswith(".pdf")] == [
        "documents/2026-04-08_obshchiy-analiz-krovi.pdf",
        "documents/2026-04-08_biokhimicheskiy-analiz-krovi.pdf",
    ]


async def test_filtered_by_date_range_and_type(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        await add_all_sources(client, created)
        export = await _export(
            client,
            created,
            {"scope": "filtered", "filter": {"type": ["conclusion"], "from": "2026-04-01"}},
        )

    assert export.json()["document_count"] == 2


async def test_selected_documents_and_duplicate_names(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        documents = await add_all_sources(client, created)
        blood, biochemistry = documents[0], documents[1]
        await client.patch(
            f"/api/v1/documents/{biochemistry['id']}",
            headers={**write_headers(created), "If-Match": '"v1"'},
            json={"title": blood["title"]},
        )
        export = await _export(
            client,
            created,
            {"scope": "selected", "document_ids": [biochemistry["id"], blood["id"]]},
        )
        _, archive = await _zip(client, export)

    assert export.json()["document_count"] == 2
    assert archive.namelist()[:2] == [
        "documents/2026-04-08_obshchiy-analiz-krovi.pdf",
        "documents/2026-04-08_obshchiy-analiz-krovi-2.pdf",
    ]


async def test_empty_export_is_422(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        export = await _export(client, created, {"scope": "all"})

    assert export.status_code == 422
    assert export.json()["code"] == "validation_error"
    assert export.json()["detail"] == "Нет документов для экспорта"


async def test_export_create_is_idempotent(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        await add_all_sources(client, created)
        headers = write_headers(created)
        first = await client.post("/api/v1/exports", headers=headers, json={"scope": "all"})
        second = await client.post("/api/v1/exports", headers=headers, json={"scope": "all"})

    assert second.headers["idempotent-replayed"] == "true"
    assert second.json() == first.json()


async def test_tc073_expired_export_is_404(api: Api, superuser_engine: AsyncEngine) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        await add_all_sources(client, created)
        export = await _export(client, created, {"scope": "all"})
        async with superuser_engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE app.exports SET created_at = now() - interval '61 minutes',"
                    " expires_at = now() - interval '1 minute' WHERE id = :id"
                ),
                {"id": export.json()["id"]},
            )
        response = await client.get(export.json()["content_url"])

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_export_of_another_archive_is_404(api: Api) -> None:
    async with api.client() as owner, api.client() as stranger:
        created = await create_archive(owner)
        await add_all_sources(owner, created)
        export = await _export(owner, created, {"scope": "all"})
        await create_archive(stranger)
        response = await stranger.get(export.json()["content_url"])

    assert response.status_code == 404
