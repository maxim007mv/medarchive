"""GET /api/v1/documents over one archive with the six task fixtures (TC-010, TC-011, TC-030..)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from api_stack import create_archive, running_api, settings_for, write_kek
from conftest import DatabaseUrls
from documents_support import EXPECTED_TITLES, SOURCES, add_all_sources
from httpx import AsyncClient

from app.storage.s3 import ObjectStorage

pytestmark = pytest.mark.asyncio(loop_scope="module")

ECG = "ЭКГ покоя"
BLOOD = ["Общий анализ крови", "Биохимический анализ крови"]


@dataclass
class Archive:
    client: AsyncClient
    documents: list[dict[str, Any]]

    async def fetch(self, **params: Any) -> dict[str, Any]:
        response = await self.client.get("/api/v1/documents", params=params)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    async def titles(self, **params: Any) -> list[str]:
        return [item["title"] for item in (await self.fetch(**params))["items"]]

    async def problem(self, **params: Any) -> tuple[int, dict[str, Any]]:
        response = await self.client.get("/api/v1/documents", params=params)
        return response.status_code, response.json()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def archive(
    database: DatabaseUrls,
    storage: ObjectStorage,
    redis_url: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[Archive]:
    kek = write_kek(tmp_path_factory.mktemp("kek") / "kek.json")
    settings = settings_for(database.app, redis_url, kek)
    async with running_api(settings, storage) as api, api.client() as client:
        created = await create_archive(client)
        yield Archive(client, await add_all_sources(client, created))


async def test_tc011_default_order(archive: Archive) -> None:
    body = await archive.fetch()

    assert [item["title"] for item in body["items"]] == EXPECTED_TITLES
    assert (body["total"], body["matched"], body["undated_excluded"]) == (6, 6, 0)
    assert body["next_page_token"] == ""


async def test_items_carry_size_and_note_flag(archive: Archive) -> None:
    items = {item["title"]: item for item in (await archive.fetch())["items"]}

    for source in SOURCES:
        item = items[source.title]
        assert item["size_bytes"] == source.size_bytes
        assert item["document_date"] == source.document_date
        assert item["has_note"] is False
        assert set(item) == {
            "id", "title", "type", "document_date", "uploaded_at", "has_note", "size_bytes",
            "version",
        }  # fmt: skip


async def test_tc010_order_by_upload_newest_first_undated_last(archive: Archive) -> None:
    titles = await archive.titles(order_by="uploaded_at desc")

    by_upload = [source.title for source in SOURCES if source.document_date][::-1]
    assert titles == [*by_upload, ECG]


@pytest.mark.parametrize("q", ["анализ", "АНАЛИЗ", "Анализ", "  анализ  ", "анали", "ий анал"])
async def test_tc030_tc031_substring_search_ignores_case(archive: Archive, q: str) -> None:
    body = await archive.fetch(q=q)

    assert [item["title"] for item in body["items"]] == BLOOD
    assert (body["total"], body["matched"], body["undated_excluded"]) == (6, 2, 0)


async def test_search_treats_yo_as_ye(archive: Archive) -> None:
    assert await archive.titles(q="почёк") == ["УЗИ почек и мочевого пузыря"]


@pytest.mark.parametrize("q", ["ан", " а ", "a"])
async def test_tc032_one_or_two_characters_are_422(archive: Archive, q: str) -> None:
    status, body = await archive.problem(q=q)

    assert status == 422
    assert body["code"] == "validation_error"
    assert body["errors"][0]["pointer"] == "/q"


async def test_whitespace_query_means_no_search(archive: Archive) -> None:
    assert (await archive.fetch(q="   "))["matched"] == 6


async def test_tc033_nothing_found(archive: Archive) -> None:
    body = await archive.fetch(q="рентген")

    assert (body["items"], body["matched"], body["total"]) == ([], 0, 6)


async def test_tc034_document_date_range_counts_undated(archive: Archive) -> None:
    body = await archive.fetch(date_field="document", **{"from": "2026-04-01", "to": "2026-04-30"})

    assert [item["title"] for item in body["items"]] == ["Заключение терапевта", *BLOOD]
    assert (body["matched"], body["undated_excluded"]) == (3, 1)


async def test_tc035_only_undated(archive: Archive) -> None:
    body = await archive.fetch(undated="true", **{"from": "2026-04-30", "to": "2026-04-01"})

    assert [item["title"] for item in body["items"]] == [ECG]
    assert (body["matched"], body["undated_excluded"]) == (1, 0)


async def test_tc036_search_and_range(archive: Archive) -> None:
    body = await archive.fetch(q="анализ", **{"from": "2026-04-01", "to": "2026-04-30"})

    assert [item["title"] for item in body["items"]] == BLOOD
    assert (body["matched"], body["undated_excluded"]) == (2, 0)


async def test_search_and_range_count_undated_matches(archive: Archive) -> None:
    body = await archive.fetch(q="покоя", **{"from": "2026-04-01"})

    assert (body["matched"], body["undated_excluded"]) == (0, 1)


async def test_tc037_upload_date_today_in_moscow(archive: Archive) -> None:
    today = datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat()

    body = await archive.fetch(
        date_field="uploaded", tz="Europe/Moscow", **{"from": today, "to": today}
    )

    assert body["matched"] == 6
    assert body["undated_excluded"] == 0


async def test_tc038_type_filter(archive: Archive) -> None:
    titles = await archive.titles(type="conclusion")

    assert titles == ["УЗИ почек и мочевого пузыря", "Заключение терапевта", ECG]
    assert len(await archive.titles(type="analysis,conclusion")) == 6


async def test_tc039_from_after_to(archive: Archive) -> None:
    status, body = await archive.problem(**{"from": "2026-04-30", "to": "2026-04-01"})

    assert status == 422
    assert body["code"] == "date_range_invalid"
    assert body["title"] == "Начало периода позже конца"
    assert body["errors"][0]["pointer"] == "/from"


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"page_size": 201}, id="page-size-201"),
        pytest.param({"page_size": 0}, id="page-size-0"),
        pytest.param({"type": "xray"}, id="unknown-type"),
        pytest.param({"tz": "Mars/Olympus"}, id="unknown-zone"),
        pytest.param({"order_by": "title asc"}, id="unknown-order"),
        pytest.param({"from": "2026-02-31"}, id="impossible-date"),
        pytest.param({"to": "0"}, id="unix-time-date"),
    ],
)
async def test_invalid_parameters_are_422(archive: Archive, params: dict[str, Any]) -> None:
    status, body = await archive.problem(**params)

    assert status == 422
    assert body["code"] == "validation_error"


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        pytest.param({}, EXPECTED_TITLES, id="TC-042-default"),
        pytest.param(
            {"order_by": "uploaded_at desc"},
            [*[s.title for s in SOURCES if s.document_date][::-1], ECG],
            id="uploaded",
        ),
        pytest.param({"q": "анализ"}, BLOOD, id="search"),
    ],
)
async def test_tc042_pages_cover_the_list_once(
    archive: Archive, params: dict[str, Any], expected: list[str]
) -> None:
    titles: list[str] = []
    ids: set[str] = set()
    token = ""
    for _ in range(10):
        body = await archive.fetch(
            page_size=2 if "q" not in params else 1, page_token=token, **params
        )
        titles += [item["title"] for item in body["items"]]
        ids |= {item["id"] for item in body["items"]}
        token = body["next_page_token"]
        if not token:
            break

    assert titles == expected
    assert len(ids) == len(expected)


@pytest.mark.parametrize(
    "changed",
    [
        pytest.param({"q": "крови"}, id="TC-043-q"),
        pytest.param({"q": "анализ", "order_by": "uploaded_at desc"}, id="order"),
        pytest.param({"q": "анализ", "tz": "UTC"}, id="tz"),
        pytest.param({"q": "анализ", "type": "analysis"}, id="type"),
    ],
)
async def test_tc043_token_from_other_parameters(archive: Archive, changed: dict[str, Any]) -> None:
    first = await archive.fetch(q="анализ", page_size=1)

    status, body = await archive.problem(
        page_size=1, page_token=first["next_page_token"], **changed
    )

    assert status == 400
    assert body["code"] == "invalid_page_token"


async def test_tampered_token_is_invalid(archive: Archive) -> None:
    status, body = await archive.problem(**{"page_token": "bm90LWEtdG9rZW4"})

    assert (status, body["code"]) == (400, "invalid_page_token")
