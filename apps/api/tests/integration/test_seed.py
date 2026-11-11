"""BE-17: the seed loads the six fixtures through uploads -> documents."""

import re
import secrets
from pathlib import Path

from api_stack import ACCESS_KEY_PATTERN, write_kek
from documents_support import EXPECTED_TITLES, REPO_ROOT, SOURCES
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli import _new_workspace, load_fixtures, seed_workspace
from app.core.crypto import Kek
from app.core.deps import load_workspace_keys, session_tx
from app.core.page_token import PageTokenCodec
from app.modules.documents import queries
from app.modules.documents.listing import ListFilter
from app.storage.s3 import ObjectStorage


def test_fixtures_come_from_the_manifest() -> None:
    fixtures = load_fixtures(REPO_ROOT)

    assert [(f.path, f.title, f.type, f.document_date) for f in fixtures] == [
        (s.path, s.title, s.type, s.date) for s in SOURCES
    ]


async def test_seed_creates_the_six_documents_of_the_task(
    app_sessions: async_sessionmaker[AsyncSession], storage: ObjectStorage, tmp_path: Path
) -> None:
    kek = Kek.from_file(write_kek(tmp_path / "kek.json"))
    async with app_sessions() as db:
        session, access_key = await _new_workspace(db, kek)
        created = await seed_workspace(db, kek, storage, session, load_fixtures(REPO_ROOT))
        async with session_tx(db, session):
            keys = await load_workspace_keys(db, kek, session.workspace_id)
        listed = await queries.list_documents(
            db,
            session,
            keys,
            PageTokenCodec([secrets.token_urlsafe(32)]),
            list_filter=ListFilter(),
            tz="Europe/Moscow",
            order_by="document_date desc",
            page_size=50,
            page_token=None,
        )

    assert re.fullmatch(ACCESS_KEY_PATTERN, access_key)
    assert sorted(item.id for item in listed.items) == sorted(created)
    assert [item.title for item in listed.items] == EXPECTED_TITLES
    by_title = {source.title: source for source in SOURCES}
    for item in listed.items:
        assert item.document_date == by_title[item.title].date
        assert item.size_bytes == by_title[item.title].size_bytes
