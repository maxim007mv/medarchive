"""DB-12 and the ORM layer: pool settings, no implicit transactions, models match migrations."""

import os
import uuid
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.db.engine import POOL_SIZE, create_engine
from app.db.models import Base, Document, DocumentFile
from app.db.transaction import workspace_tx
from db.support import Cluster, Sessions

MakeWorkspace = Callable[[], Awaitable[uuid.UUID]]
MakeDocument = Callable[[uuid.UUID], Awaitable[uuid.UUID]]

_COLUMNS = text(
    """SELECT c.relname, a.attname, NOT a.attnotnull AS nullable,
  format_type(a.atttypid, a.atttypmod) AS type
FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
WHERE c.relnamespace = 'app'::regnamespace AND c.relkind IN ('r', 'p') AND NOT c.relispartition
  AND a.attnum > 0 AND NOT a.attisdropped"""
)


async def test_db12_engine_uses_pool_of_ten_and_five_second_statement_timeout(
    migrated: Cluster,
) -> None:
    engine = create_engine(migrated.url("ma_app"))
    async with engine.connect() as connection:
        timeout = (await connection.execute(text("SHOW statement_timeout"))).scalar()
    pool = engine.pool
    await engine.dispose()

    assert isinstance(pool, AsyncAdaptedQueuePool)
    assert (pool.size(), timeout) == (POOL_SIZE, "5s")


async def test_db04_statement_outside_a_transaction_is_refused(sessions: Sessions) -> None:
    async with sessions.app() as session:
        with pytest.raises(InvalidRequestError, match="Autobegin is disabled"):
            await session.execute(text("SELECT 1"))


async def test_models_match_the_migrated_schema(sessions: Sessions) -> None:
    async with sessions.superuser() as session, session.begin():
        database = {
            (row.relname, row.attname): (row.nullable, row.type)
            for row in (await session.execute(_COLUMNS)).all()
        }
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    # Generated columns carry no NOT NULL in the DDL; list_key is never NULL by its expression.
    models = {
        (table.name, column.name): (
            bool(column.nullable) or column.computed is not None,
            column.type.compile(dialect=dialect).lower().replace("char(", "character("),
        )
        for table in Base.metadata.tables.values()
        for column in table.columns
    }

    assert models == database


async def test_relationships_raise_unless_loaded_explicitly(
    sessions: Sessions, make_workspace: MakeWorkspace, make_document: MakeDocument
) -> None:
    workspace_id = await make_workspace()
    document_id = await make_document(workspace_id)
    async with sessions.app() as session, workspace_tx(session, workspace_id):
        session.add(
            DocumentFile(
                document_id=document_id,
                workspace_id=workspace_id,
                object_key=f"ws/{workspace_id}/{document_id}.bin",
                size_bytes=1,
                sha256=os.urandom(32),
                original_name_ct=os.urandom(40),
            )
        )

    async with sessions.app() as session, workspace_tx(session, workspace_id):
        lazy = (await session.execute(select(Document))).scalar_one()
        with pytest.raises(InvalidRequestError, match="lazy='raise'"):
            _ = lazy.file
        session.expunge_all()
        loaded = (
            await session.execute(select(Document).options(selectinload(Document.file)))
        ).scalar_one()

    assert loaded.file is not None
    assert loaded.file.object_key == f"ws/{workspace_id}/{document_id}.bin"


async def test_update_returns_version_and_updated_at_set_by_trigger(
    sessions: Sessions, make_workspace: MakeWorkspace, make_document: MakeDocument
) -> None:
    workspace_id = await make_workspace()
    document_id = await make_document(workspace_id)

    async with sessions.app() as session, workspace_tx(session, workspace_id):
        document = await session.get_one(Document, document_id)
        uploaded_at = document.uploaded_at
        document.type_code = "conclusion"
        await session.flush()

    assert document.version == 2
    assert document.updated_at > uploaded_at
