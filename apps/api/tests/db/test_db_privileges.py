"""DB-02, DB-08: least privilege for ma_app and ma_worker, append-only audit, pinned functions."""

import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.transaction import workspace_tx
from db.support import INSUFFICIENT_PRIVILEGE, Sessions, sqlstate

MakeWorkspace = Callable[[], Awaitable[uuid.UUID]]
MakeDocument = Callable[[uuid.UUID], Awaitable[uuid.UUID]]

SCHEMA_CHANGES = (
    "ALTER TABLE app.documents ADD COLUMN extra integer",
    "ALTER TABLE app.documents DISABLE ROW LEVEL SECURITY",
    "DROP TABLE app.documents",
    "TRUNCATE app.documents",
    "CREATE TABLE app.extra (id integer)",
    "CREATE TABLE public.extra (id integer)",
    "CREATE INDEX extra ON app.documents (type_code)",
    "DROP POLICY ws_isolation ON app.documents",
    "DROP FUNCTION app.current_workspace()",
    "CREATE FUNCTION app.extra() RETURNS integer LANGUAGE sql AS 'SELECT 1'",
)
APP_FORBIDDEN = (
    "SELECT id FROM app.sessions",
    "SELECT id FROM app.access_keys",
    "SELECT object_key FROM app.purge_queue",
    "SELECT key_sha256 FROM app.workspace_create_keys",
    "INSERT INTO app.workspaces (id, dek_ciphertext, kek_key_id)"
    " VALUES (app.current_workspace(), gen_random_bytes(64), 'kek-1')",
    "UPDATE app.workspaces SET kek_key_id = 'kek-2'",
    "DELETE FROM app.documents",
    "SELECT id FROM app.audit_log",
    "UPDATE app.audit_log SET action = 'document.view'",
    "DELETE FROM app.audit_log",
    "SELECT id FROM app.audit_log_default",
    "INSERT INTO app.audit_log_default (workspace_id, action)"
    " VALUES (app.current_workspace(), 'document.view')",
    "SELECT app.workspaces_due_for_purge(500)",
    "SELECT app.ensure_audit_partitions()",
    "SELECT app.require_workspace()",
)
WORKER_FORBIDDEN = (
    "SELECT id FROM app.sessions",
    "SELECT id FROM app.access_keys",
    "SELECT id FROM app.consents",
    "SELECT key_sha256 FROM app.workspace_create_keys",
    "INSERT INTO app.documents (id, workspace_id, type_code, title_ct, title_bidx)"
    " VALUES (gen_random_uuid(), app.current_workspace(), 'other', gen_random_bytes(40), '{1}')",
    "UPDATE app.audit_log SET action = 'document.view'",
    "DELETE FROM app.audit_log",
    "SELECT id FROM app.audit_log",
    "SELECT app.create_session(gen_random_bytes(32), interval '1 day', interval '2 days')",
    "SELECT app.enqueue_purge('ws/x', 'orphan')",
)
# Every SECURITY DEFINER function of schema app: owner and the only role allowed to call it.
DEFINER_FUNCTIONS = {
    "app.resolve_session(bytea)": ("ma_auth", "ma_app"),
    "app.find_access_key(text)": ("ma_auth", "ma_app"),
    "app.create_workspace(bytea,text,text,bytea)": ("ma_auth", "ma_app"),
    "app.create_session(bytea,interval,interval)": ("ma_auth", "ma_app"),
    "app.touch_session(uuid,interval)": ("ma_auth", "ma_app"),
    "app.revoke_sessions(uuid)": ("ma_auth", "ma_app"),
    "app.issue_access_key(text,text)": ("ma_auth", "ma_app"),
    "app.revoke_access_key()": ("ma_auth", "ma_app"),
    "app.delete_workspace()": ("ma_auth", "ma_app"),
    "app.soft_delete_document(uuid)": ("ma_auth", "ma_app"),
    "app.enqueue_purge(text,text)": ("ma_auth", "ma_app"),
    "app.claim_workspace_create_key(bytea,bytea)": ("ma_auth", "ma_app"),
    "app.complete_workspace_create_key(bytea,integer,bytea)": ("ma_auth", "ma_app"),
    "app.release_workspace_create_key(bytea)": ("ma_auth", "ma_app"),
    "app.workspaces_due_for_purge(integer)": ("ma_auth", "ma_worker"),
    "app.purge_expired_workspace_create_keys(integer)": ("ma_auth", "ma_worker"),
    "app.ensure_audit_partitions()": ("ma_owner", "ma_worker"),
}
_DEFINER_ACL = text(
    """SELECT p.oid::regprocedure::text AS signature, r.rolname AS owner, p.proconfig,
  has_function_privilege('ma_app', p.oid, 'EXECUTE') AS app,
  has_function_privilege('ma_worker', p.oid, 'EXECUTE') AS worker,
  EXISTS (SELECT 1 FROM aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
          WHERE a.grantee = 0) AS public
FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner
WHERE p.pronamespace = 'app'::regnamespace AND p.prosecdef"""
)


async def _expect_denied(
    sessions: Sessions, role: str, workspace_id: uuid.UUID, statement: str
) -> None:
    maker = sessions.app if role == "ma_app" else sessions.worker
    with pytest.raises(DBAPIError, match=r"permission denied|must be owner") as error:
        async with maker() as session, workspace_tx(session, workspace_id):
            await session.execute(text(statement))
    assert sqlstate(error.value) == INSUFFICIENT_PRIVILEGE


@pytest.mark.parametrize("role", ["ma_app", "ma_worker"])
@pytest.mark.parametrize("statement", SCHEMA_CHANGES)
async def test_db02_roles_cannot_change_schema(
    sessions: Sessions, make_workspace: MakeWorkspace, role: str, statement: str
) -> None:
    await _expect_denied(sessions, role, await make_workspace(), statement)


@pytest.mark.parametrize("statement", APP_FORBIDDEN)
async def test_db02_app_has_no_direct_access_to_login_purge_and_audit(
    sessions: Sessions, make_workspace: MakeWorkspace, statement: str
) -> None:
    await _expect_denied(sessions, "ma_app", await make_workspace(), statement)


@pytest.mark.parametrize("statement", WORKER_FORBIDDEN)
async def test_db02_worker_has_no_access_to_login_tables_or_app_functions(
    sessions: Sessions, make_workspace: MakeWorkspace, statement: str
) -> None:
    await _expect_denied(sessions, "ma_worker", await make_workspace(), statement)


async def test_db02_definer_functions_pin_search_path_and_have_one_caller(
    sessions: Sessions,
) -> None:
    async with sessions.superuser() as session, session.begin():
        rows = (await session.execute(_DEFINER_ACL)).all()

    callers = {
        row.signature: (row.owner, "ma_app" if row.app else "ma_worker")
        for row in rows
        if row.app != row.worker
    }
    assert callers == DEFINER_FUNCTIONS
    assert {row.signature for row in rows} == set(DEFINER_FUNCTIONS)
    assert all(row.proconfig == ["search_path=pg_catalog, pg_temp"] for row in rows)
    assert not any(row.public for row in rows)


async def test_db08_audit_trigger_records_field_names_without_values(
    sessions: Sessions, make_workspace: MakeWorkspace, make_document: MakeDocument
) -> None:
    workspace_id = await make_workspace()
    document_id = await make_document(workspace_id)
    session_id = uuid.uuid4()
    new_title = os.urandom(48)

    async with (
        sessions.app() as session,
        workspace_tx(session, workspace_id, session_id=session_id, request_id="req_9"),
    ):
        await session.execute(
            text("UPDATE app.documents SET title_ct = :title, note_ct = :note WHERE id = :id"),
            {"title": new_title, "note": os.urandom(40), "id": document_id},
        )
    async with sessions.superuser() as session, session.begin():
        rows = (
            await session.execute(
                text(
                    "SELECT action, changed_fields, session_id, request_id FROM app.audit_log"
                    " WHERE entity_id = :id ORDER BY id"
                ),
                {"id": document_id},
            )
        ).all()

    assert [tuple(row) for row in rows] == [
        ("document.create", None, None, ""),
        ("document.update", ["title", "note"], session_id, "req_9"),
    ]


async def test_db08_partitions_have_no_grants(sessions: Sessions) -> None:
    async with sessions.superuser() as session, session.begin():
        granted = (
            await session.execute(
                text(
                    "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid"
                    " WHERE i.inhparent = 'app.audit_log'::regclass AND c.relacl IS NOT NULL"
                )
            )
        ).all()

    assert granted == []


async def test_db08_worker_keeps_audit_partitions_two_months_ahead(sessions: Sessions) -> None:
    today = datetime.now(UTC)
    first = today.year * 12 + today.month - 1
    expected = {f"audit_log_{i // 12:04d}_{i % 12 + 1:02d}" for i in range(first, first + 3)}

    async with sessions.worker() as session, session.begin():
        created = (await session.execute(text("SELECT app.ensure_audit_partitions()"))).scalar()
    async with sessions.superuser() as session, session.begin():
        partitions = set(
            (
                await session.execute(
                    text(
                        "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid"
                        " WHERE i.inhparent = 'app.audit_log'::regclass"
                    )
                )
            ).scalars()
        )

    assert created == 0
    assert expected <= partitions
