"""DB-02, DB-09, ADR-044: login, deletion and purge paths through the 0002 functions."""

import os
import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import Row, text
from sqlalchemy.exc import DBAPIError

from app.db.transaction import workspace_tx
from db.support import INSUFFICIENT_PRIVILEGE, Sessions, sqlstate

MakeWorkspace = Callable[[], Awaitable[uuid.UUID]]
MakeDocument = Callable[[uuid.UUID], Awaitable[uuid.UUID]]

IDLE, ABSOLUTE = timedelta(days=30), timedelta(days=180)
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _lookup_id() -> str:
    return "".join(secrets.choice(CROCKFORD) for _ in range(6))


async def _rows(
    sessions: Sessions,
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    workspace_id: uuid.UUID | None = None,
    role: str = "ma_app",
) -> list[Row[Any]]:
    maker = {"ma_app": sessions.app, "ma_worker": sessions.worker, "postgres": sessions.superuser}
    async with maker[role]() as session:
        if workspace_id is None:
            async with session.begin():
                result = await session.execute(text(sql), params or {})
        else:
            async with workspace_tx(session, workspace_id):
                result = await session.execute(text(sql), params or {})
    return list(result.all())


async def _create_session(sessions: Sessions, workspace_id: uuid.UUID, token: bytes) -> Row[Any]:
    rows = await _rows(
        sessions,
        "SELECT * FROM app.create_session(:token, :idle, :absolute)",
        {"token": token, "idle": IDLE, "absolute": ABSOLUTE},
        workspace_id=workspace_id,
    )
    return rows[0]


async def _resolve(sessions: Sessions, token: bytes) -> list[tuple[Any, ...]]:
    rows = await _rows(sessions, "SELECT * FROM app.resolve_session(:token)", {"token": token})
    return [tuple(row) for row in rows]


async def test_db02_create_workspace_requires_context(sessions: Sessions) -> None:
    with pytest.raises(DBAPIError, match=r"app\.workspace_id is not set") as error:
        await _rows(
            sessions,
            "SELECT app.create_workspace(:dek, 'kek-1', '2026-11-10', :evidence)",
            {"dek": os.urandom(64), "evidence": os.urandom(32)},
        )

    assert sqlstate(error.value) == INSUFFICIENT_PRIVILEGE


async def test_db02_create_workspace_writes_workspace_and_active_consent(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    workspace_id = await make_workspace()

    rows = await _rows(
        sessions,
        "SELECT w.kek_key_id, c.policy_version, c.withdrawn_at"
        " FROM app.workspaces w JOIN app.consents c ON c.workspace_id = w.id",
        workspace_id=workspace_id,
    )

    assert [tuple(row) for row in rows] == [("kek-1", "2026-11-10", None)]


async def test_db02_session_resolves_touches_within_absolute_limit_and_revokes(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    workspace_id, token = await make_workspace(), os.urandom(32)
    created = await _create_session(sessions, workspace_id, token)

    resolved = await _resolve(sessions, token)
    touched = await _rows(
        sessions,
        "SELECT app.touch_session(:id, :idle)",
        {"id": created.session_id, "idle": timedelta(days=400)},
        workspace_id=workspace_id,
    )
    revoked = await _rows(
        sessions,
        "SELECT app.revoke_sessions(:id)",
        {"id": created.session_id},
        workspace_id=workspace_id,
    )
    touched_after_revoke = await _rows(
        sessions,
        "SELECT app.touch_session(:id, :idle)",
        {"id": created.session_id, "idle": IDLE},
        workspace_id=workspace_id,
    )

    assert created.absolute_expires_at - created.idle_expires_at == ABSOLUTE - IDLE
    assert resolved == [(created.session_id, workspace_id)]
    assert touched[0][0] == created.absolute_expires_at
    assert revoked[0][0] == 1
    assert await _resolve(sessions, token) == []
    assert touched_after_revoke[0][0] is None


async def test_db02_revoke_sessions_without_id_revokes_all_of_the_workspace_only(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    workspace_id, other = await make_workspace(), await make_workspace()
    tokens = [os.urandom(32) for _ in range(3)]
    for token in tokens[:2]:
        await _create_session(sessions, workspace_id, token)
    await _create_session(sessions, other, tokens[2])

    revoked = await _rows(sessions, "SELECT app.revoke_sessions()", workspace_id=workspace_id)

    assert revoked[0][0] == 2
    assert [await _resolve(sessions, token) != [] for token in tokens] == [False, False, True]


async def test_db02_session_cannot_be_touched_from_another_workspace(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    workspace_id, other = await make_workspace(), await make_workspace()
    created = await _create_session(sessions, workspace_id, os.urandom(32))

    touched = await _rows(
        sessions,
        "SELECT app.touch_session(:id, :idle)",
        {"id": created.session_id, "idle": IDLE},
        workspace_id=other,
    )
    revoked = await _rows(
        sessions, "SELECT app.revoke_sessions(:id)", {"id": created.session_id}, workspace_id=other
    )

    assert (touched[0][0], revoked[0][0]) == (None, 0)


async def test_db02_issue_access_key_revokes_the_previous_one(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    workspace_id = await make_workspace()
    old_lookup, new_lookup = _lookup_id(), _lookup_id()
    issue = "SELECT * FROM app.issue_access_key(:lookup, :hash)"

    first = await _rows(
        sessions, issue, {"lookup": old_lookup, "hash": "$argon2id$old"}, workspace_id=workspace_id
    )
    second = await _rows(
        sessions, issue, {"lookup": new_lookup, "hash": "$argon2id$new"}, workspace_id=workspace_id
    )
    find = "SELECT * FROM app.find_access_key(:lookup)"
    old_found = await _rows(sessions, find, {"lookup": old_lookup})
    new_found = await _rows(sessions, find, {"lookup": new_lookup})

    assert first[0].revoked_previous is False
    assert second[0].revoked_previous is True
    assert old_found == []
    assert [tuple(row) for row in new_found] == [
        (second[0].access_key_id, workspace_id, "$argon2id$new")
    ]


async def test_db02_delete_workspace_erases_keys_and_closes_every_way_in(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    workspace_id, token, lookup = await make_workspace(), os.urandom(32), _lookup_id()
    await _create_session(sessions, workspace_id, token)
    await _rows(
        sessions,
        "SELECT * FROM app.issue_access_key(:lookup, '$argon2id$x')",
        {"lookup": lookup},
        workspace_id=workspace_id,
    )

    first = await _rows(sessions, "SELECT app.delete_workspace()", workspace_id=workspace_id)
    second = await _rows(sessions, "SELECT app.delete_workspace()", workspace_id=workspace_id)
    state = await _rows(
        sessions,
        "SELECT w.dek_ciphertext, w.purge_after - w.deleted_at AS grace,"
        " (SELECT count(*) FROM app.consents c WHERE c.withdrawn_at IS NULL) AS active_consents"
        " FROM app.workspaces w",
        workspace_id=workspace_id,
    )
    new_session = await _rows(
        sessions,
        "SELECT * FROM app.create_session(:token, :idle, :absolute)",
        {"token": os.urandom(32), "idle": IDLE, "absolute": ABSOLUTE},
        workspace_id=workspace_id,
    )
    new_key = await _rows(
        sessions,
        "SELECT * FROM app.issue_access_key(:lookup, '$argon2id$y')",
        {"lookup": _lookup_id()},
        workspace_id=workspace_id,
    )

    assert first[0][0] is not None
    assert second[0][0] is None
    assert [tuple(row) for row in state] == [(None, timedelta(hours=24), 0)]
    assert await _resolve(sessions, token) == []
    assert await _rows(sessions, "SELECT * FROM app.find_access_key(:l)", {"l": lookup}) == []
    assert (new_session, new_key) == ([], [])


async def test_db02_soft_delete_document_only_in_the_current_workspace(
    sessions: Sessions, make_workspace: MakeWorkspace, make_document: MakeDocument
) -> None:
    workspace_id, other = await make_workspace(), await make_workspace()
    document_id = await make_document(workspace_id)

    async def soft_delete(workspace: uuid.UUID) -> bool:
        rows = await _rows(
            sessions,
            "SELECT app.soft_delete_document(:id)",
            {"id": document_id},
            workspace_id=workspace,
        )
        deleted: bool = rows[0][0]
        return deleted

    assert [await soft_delete(other), await soft_delete(workspace_id)] == [False, True]
    assert await soft_delete(workspace_id) is False
    audit = await _rows(
        sessions,
        "SELECT action FROM app.audit_log WHERE entity_id = :id ORDER BY id",
        {"id": document_id},
        role="postgres",
    )
    assert [row.action for row in audit] == ["document.create", "document.delete"]


async def test_db02_enqueue_purge_accepts_only_objects_of_the_current_workspace(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    workspace_id, other = await make_workspace(), await make_workspace()
    object_id = uuid.uuid4()
    enqueue = "SELECT app.enqueue_purge(:key, :reason)"
    own_keys = [f"ws/{workspace_id}/{object_id}.bin", f"q/{workspace_id}/{object_id}.bin"]

    for key in [*own_keys, own_keys[0]]:
        await _rows(
            sessions, enqueue, {"key": key, "reason": "document_deleted"}, workspace_id=workspace_id
        )
    for foreign_key in (
        f"ws/{other}/{object_id}.bin",
        f"ws/{workspace_id}/../{other}/{object_id}.bin",
        f"ws/{workspace_id}/{object_id}.bin.extra",
    ):
        with pytest.raises(DBAPIError, match="outside the current workspace"):
            await _rows(
                sessions,
                enqueue,
                {"key": foreign_key, "reason": "orphan"},
                workspace_id=workspace_id,
            )
    queued = await _rows(
        sessions,
        "SELECT object_key FROM app.purge_queue WHERE object_key LIKE :prefix ORDER BY 1",
        {"prefix": f"%/{workspace_id}/%"},
        role="ma_worker",
    )

    assert [row.object_key for row in queued] == sorted(own_keys)


async def test_db09_worker_finds_due_workspaces_and_purges_under_rls(
    sessions: Sessions, make_workspace: MakeWorkspace, make_document: MakeDocument
) -> None:
    with_deleted_document, deleted_workspace = await make_workspace(), await make_workspace()
    document_id = await make_document(with_deleted_document)
    await _rows(
        sessions,
        "SELECT app.soft_delete_document(:id)",
        {"id": document_id},
        workspace_id=with_deleted_document,
    )
    await _create_session(sessions, deleted_workspace, os.urandom(32))
    await _rows(sessions, "SELECT app.delete_workspace()", workspace_id=deleted_workspace)
    due = "SELECT workspace_id FROM app.workspaces_due_for_purge(500)"

    before_grace = {row.workspace_id for row in await _rows(sessions, due, role="ma_worker")}
    await _rows(
        sessions,
        "UPDATE app.documents SET deleted_at = now() - interval '25 hours' WHERE id = :id"
        " RETURNING id",
        {"id": document_id},
        role="postgres",
    )
    await _rows(
        sessions,
        "UPDATE app.workspaces SET deleted_at = now() - interval '25 hours',"
        " purge_after = now() - interval '1 hour' WHERE id = :id RETURNING id",
        {"id": deleted_workspace},
        role="postgres",
    )
    after_grace = {row.workspace_id for row in await _rows(sessions, due, role="ma_worker")}
    purged_documents = await _rows(
        sessions,
        "DELETE FROM app.documents WHERE deleted_at <= now() - interval '24 hours' RETURNING id",
        workspace_id=with_deleted_document,
        role="ma_worker",
    )
    purged_workspaces = await _rows(
        sessions,
        "DELETE FROM app.workspaces WHERE purge_after <= now() RETURNING id",
        workspace_id=deleted_workspace,
        role="ma_worker",
    )
    leftovers = await _rows(
        sessions,
        "SELECT (SELECT count(*) FROM app.sessions WHERE workspace_id = :w)"
        " + (SELECT count(*) FROM app.consents WHERE workspace_id = :w)",
        {"w": deleted_workspace},
        role="postgres",
    )
    still_due = {row.workspace_id for row in await _rows(sessions, due, role="ma_worker")}

    assert {with_deleted_document, deleted_workspace}.isdisjoint(before_grace)
    assert {with_deleted_document, deleted_workspace} <= after_grace
    assert [row.id for row in purged_documents] == [document_id]
    assert [row.id for row in purged_workspaces] == [deleted_workspace]
    assert leftovers[0][0] == 0
    assert {with_deleted_document, deleted_workspace}.isdisjoint(still_due)


async def test_db09_due_scan_is_capped(sessions: Sessions) -> None:
    rows = await _rows(
        sessions, "SELECT count(*) FROM app.workspaces_due_for_purge(-1)", role="ma_worker"
    )

    assert rows[0][0] == 0
