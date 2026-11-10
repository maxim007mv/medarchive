"""TC-091, TC-092, DB-03, DB-04: workspace isolation by row-level security."""

import os
import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.models import (
    Base,
    Consent,
    Document,
    DocumentFile,
    Export,
    IdempotencyKey,
    Upload,
    Workspace,
)
from app.db.transaction import workspace_tx
from db.support import INSUFFICIENT_PRIVILEGE, Cluster, Sessions, sqlstate

MakeWorkspace = Callable[[], Awaitable[uuid.UUID]]
MakeDocument = Callable[[uuid.UUID], Awaitable[uuid.UUID]]

APP_TABLES: tuple[type[Base], ...] = (
    Workspace,
    Consent,
    Upload,
    Document,
    DocumentFile,
    IdempotencyKey,
    Export,
)
WORKER_TABLES: tuple[type[Base], ...] = (
    Workspace,
    Upload,
    Document,
    DocumentFile,
    IdempotencyKey,
    Export,
)
CONTEXT = text(
    "SELECT app.current_workspace(), current_setting('app.session_id', true),"
    " current_setting('app.request_id', true), pg_backend_pid()"
)


async def _counts(session: AsyncSession, tables: tuple[type[Base], ...]) -> dict[str, int]:
    return {
        table.__tablename__: (
            await session.execute(select(func.count()).select_from(table))
        ).scalar_one()
        for table in tables
    }


async def _fill(sessions: Sessions, workspace_id: uuid.UUID) -> None:
    """One row in every workspace table, so that "0 rows" below is not vacuous."""
    document_id = uuid.uuid4()
    async with sessions.app() as session, workspace_tx(session, workspace_id):
        session.add(
            Document(
                id=document_id,
                workspace_id=workspace_id,
                type_code="analysis",
                title_ct=os.urandom(40),
                title_bidx=[1, 2],
            )
        )
        await session.flush()
        session.add_all(
            [
                DocumentFile(
                    document_id=document_id,
                    workspace_id=workspace_id,
                    object_key=f"ws/{workspace_id}/{document_id}.bin",
                    size_bytes=100,
                    sha256=os.urandom(32),
                    original_name_ct=os.urandom(40),
                ),
                Upload(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    quarantine_key=f"q/{workspace_id}/{uuid.uuid4()}.bin",
                    max_bytes=100,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                ),
                IdempotencyKey(
                    workspace_id=workspace_id,
                    key=secrets.token_hex(16),
                    operation="documents.create",
                    fingerprint=os.urandom(32),
                ),
                Export(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    scope="all",
                    document_ids=[document_id],
                    total_bytes=100,
                ),
            ]
        )


async def test_tc091_without_context_app_and_worker_see_no_rows(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    workspace_id = await make_workspace()
    await _fill(sessions, workspace_id)

    async with sessions.app() as session, workspace_tx(session, workspace_id):
        with_context = await _counts(session, APP_TABLES)
    async with sessions.app() as session, session.begin():
        app_without_context = await _counts(session, APP_TABLES)
    async with sessions.worker() as session, session.begin():
        worker_without_context = await _counts(session, WORKER_TABLES)

    assert all(count >= 1 for count in with_context.values()), with_context
    assert app_without_context == dict.fromkeys(app_without_context, 0)
    assert worker_without_context == dict.fromkeys(worker_without_context, 0)


async def test_tc092_context_is_cleared_after_commit_and_rollback(migrated: Cluster) -> None:
    engine = create_async_engine(migrated.url("ma_app"), poolclass=NullPool)
    workspace_id, session_id = uuid.uuid4(), uuid.uuid4()
    async with engine.connect() as connection:
        session = AsyncSession(bind=connection, autobegin=False)
        async with workspace_tx(session, workspace_id, session_id=session_id, request_id="req_1"):
            inside = (await session.execute(CONTEXT)).one()
        async with session.begin():
            after_commit = (await session.execute(CONTEXT)).one()
        with pytest.raises(LookupError):
            async with workspace_tx(session, workspace_id):
                raise LookupError
        async with session.begin():
            after_rollback = (await session.execute(CONTEXT)).one()
    await engine.dispose()

    pid = inside[3]
    assert tuple(inside) == (workspace_id, str(session_id), "req_1", pid)
    assert tuple(after_commit) == (None, "", "", pid)
    assert tuple(after_rollback) == (None, "", "", pid)


async def test_db04_workspace_tx_must_open_the_transaction(sessions: Sessions) -> None:
    async with sessions.app() as session, session.begin():
        with pytest.raises(RuntimeError, match="must open the transaction"):
            async with workspace_tx(session, uuid.uuid4()):
                pass


async def test_db03_cross_workspace_select_update_delete_by_id_hit_nothing(
    sessions: Sessions, make_workspace: MakeWorkspace, make_document: MakeDocument
) -> None:
    own, foreign = await make_workspace(), await make_workspace()
    foreign_document = await make_document(foreign)
    params = {"id": foreign_document, "workspace_id": foreign}

    async with sessions.app() as session, workspace_tx(session, own):
        selected = (
            await session.execute(text("SELECT id FROM app.documents WHERE id = :id"), params)
        ).all()
        updated = (
            await session.execute(
                text("UPDATE app.documents SET type_code = 'analysis' WHERE id = :id RETURNING id"),
                params,
            )
        ).all()
        updated_consents = (
            await session.execute(
                text(
                    "UPDATE app.consents SET withdrawn_at = now()"
                    " WHERE workspace_id = :workspace_id RETURNING id"
                ),
                params,
            )
        ).all()
        deleted_by_function = (
            await session.execute(
                text("SELECT app.soft_delete_document(:id)"), {"id": foreign_document}
            )
        ).scalar_one()
    async with sessions.worker() as session, workspace_tx(session, own):
        deleted = (
            await session.execute(
                text("DELETE FROM app.documents WHERE id = :id RETURNING id"), params
            )
        ).all()
    async with sessions.app() as session, workspace_tx(session, foreign):
        untouched = (
            await session.execute(
                text("SELECT type_code, version FROM app.documents WHERE id = :id"), params
            )
        ).one()

    assert (selected, updated, updated_consents, deleted_by_function, deleted) == (
        [],
        [],
        [],
        False,
        [],
    )
    assert tuple(untouched) == ("other", 1)


async def test_db03_insert_into_foreign_workspace_is_rejected(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    own, foreign = await make_workspace(), await make_workspace()

    with pytest.raises(DBAPIError, match="row-level security") as error:
        async with sessions.app() as session, workspace_tx(session, own):
            session.add(
                Document(
                    id=uuid.uuid4(),
                    workspace_id=foreign,
                    type_code="other",
                    title_ct=os.urandom(40),
                    title_bidx=[1],
                )
            )

    assert sqlstate(error.value) == INSUFFICIENT_PRIVILEGE


async def test_db03_deleted_document_is_hidden_from_app_but_not_from_worker(
    sessions: Sessions, make_workspace: MakeWorkspace, make_document: MakeDocument
) -> None:
    workspace_id = await make_workspace()
    document_id = await make_document(workspace_id)
    query = text("SELECT id FROM app.documents WHERE id = :id AND deleted_at IS NOT NULL")

    async with sessions.app() as session, workspace_tx(session, workspace_id):
        await session.execute(text("SELECT app.soft_delete_document(:id)"), {"id": document_id})
    async with sessions.app() as session, workspace_tx(session, workspace_id):
        app_sees = (await session.execute(query, {"id": document_id})).scalars().all()
    async with sessions.worker() as session, workspace_tx(session, workspace_id):
        worker_sees = (await session.execute(query, {"id": document_id})).scalars().all()

    assert (app_sees, worker_sees) == ([], [document_id])
