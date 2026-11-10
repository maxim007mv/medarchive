"""TC-044: day boundaries of the upload date filter in the user's zone."""

from datetime import datetime
from typing import Any

import pytest
from api_stack import Api, create_archive
from documents_support import SOURCES, add_source
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def _set_uploaded_at(superuser: AsyncEngine, document_id: str, moment: str) -> None:
    # uploaded_at is immutable by trigger; replica mode skips triggers for this one session.
    async with superuser.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        await connection.execute(
            text("UPDATE app.documents SET uploaded_at = :at WHERE id = :id"),
            {"at": datetime.fromisoformat(moment), "id": document_id},
        )


@pytest.mark.parametrize(
    ("day", "tz", "expected"),
    [
        pytest.param("2026-11-10", "Europe/Moscow", ["late"], id="TC-044-23:59-in"),
        pytest.param("2026-11-11", "Europe/Moscow", ["after-midnight"], id="00:30-next-day"),
        pytest.param("2026-11-10", "UTC", ["late", "after-midnight"], id="same-moments-in-utc"),
    ],
)
async def test_tc044_upload_day_boundaries(
    api: Api, superuser_engine: AsyncEngine, day: str, tz: str, expected: list[str]
) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        late = await add_source(client, created, SOURCES[0])
        after_midnight = await add_source(client, created, SOURCES[1])
        await _set_uploaded_at(superuser_engine, late["id"], "2026-11-10T23:59:00+03:00")
        await _set_uploaded_at(superuser_engine, after_midnight["id"], "2026-11-11T00:30:00+03:00")
        params: dict[str, Any] = {"date_field": "uploaded", "tz": tz, "from": day, "to": day}
        response = await client.get("/api/v1/documents", params=params)

    names = {late["id"]: "late", after_midnight["id"]: "after-midnight"}
    assert sorted(names[item["id"]] for item in response.json()["items"]) == sorted(expected)
