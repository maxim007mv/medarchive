"""DB-07, ADR-045: idempotency keys of workspace operations and of POST /workspaces."""

import os
import secrets
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.transaction import workspace_tx
from db.support import Sessions, sqlstate

MakeWorkspace = Callable[[], Awaitable[uuid.UUID]]

CHECK_VIOLATION = "23514"
# Two statements on purpose: in READ COMMITTED the SELECT takes a new snapshot, so it sees a row
# that a concurrent transaction committed while this INSERT waited on the key.
CLAIM = text(
    "INSERT INTO app.idempotency_keys (workspace_id, key, operation, fingerprint)"
    " VALUES (app.current_workspace(), :key, :operation, :fingerprint)"
    " ON CONFLICT (workspace_id, key) DO NOTHING RETURNING state"
)
EXISTING = text(
    "SELECT operation, fingerprint, state, response_status, response_body_ct"
    " FROM app.idempotency_keys WHERE workspace_id = app.current_workspace() AND key = :key"
)
COMPLETE = text(
    "UPDATE app.idempotency_keys SET state = 'completed', response_status = 201,"
    " response_body_ct = :body WHERE workspace_id = app.current_workspace() AND key = :key"
)
CLAIM_CREATE = text("SELECT * FROM app.claim_workspace_create_key(:key, :fingerprint)")


async def _claim(session: AsyncSession, params: dict[str, Any]) -> list[str]:
    return list((await session.execute(CLAIM, params)).scalars())


async def test_db07_insert_on_conflict_returns_the_stored_response(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    workspace_id, other = await make_workspace(), await make_workspace()
    body = os.urandom(64)
    params = {
        "key": secrets.token_hex(16),
        "operation": "uploads.create",
        "fingerprint": os.urandom(32),
        "body": body,
    }

    async with sessions.app() as session, workspace_tx(session, workspace_id):
        first = await _claim(session, params)
        await session.execute(COMPLETE, params)
    async with sessions.app() as session, workspace_tx(session, workspace_id):
        replay = await _claim(session, params)
        stored = (await session.execute(EXISTING, params)).one()
    async with sessions.app() as session, workspace_tx(session, other):
        same_key_elsewhere = await _claim(session, params)

    assert first == ["in_progress"]
    assert replay == []
    assert tuple(stored) == ("uploads.create", params["fingerprint"], "completed", 201, body)
    assert same_key_elsewhere == ["in_progress"]


async def test_db07_failed_attempt_is_released_and_can_be_retried(
    sessions: Sessions, make_workspace: MakeWorkspace
) -> None:
    workspace_id = await make_workspace()
    params = {
        "key": secrets.token_hex(16),
        "operation": "workspace.rotateKey",
        "fingerprint": os.urandom(32),
    }

    async with sessions.app() as session, workspace_tx(session, workspace_id):
        await _claim(session, params)
    async with sessions.app() as session, workspace_tx(session, workspace_id):
        released = (
            await session.execute(
                text(
                    "DELETE FROM app.idempotency_keys WHERE workspace_id = app.current_workspace()"
                    " AND key = :key AND state = 'in_progress' RETURNING key"
                ),
                params,
            )
        ).all()
        retried = await _claim(session, params)

    assert (len(released), retried) == (1, ["in_progress"])


@pytest.mark.parametrize(
    ("operation", "state", "body"),
    [
        ("workspaces.create", "in_progress", None),
        ("documents.create", "in_progress", b"\x00" * 40),
    ],
    ids=["unknown_operation", "body_before_completion"],
)
async def test_db07_checks_reject_bad_rows(
    sessions: Sessions, make_workspace: MakeWorkspace, operation: str, state: str, body: bytes
) -> None:
    workspace_id = await make_workspace()

    with pytest.raises(DBAPIError) as error:
        async with sessions.app() as session, workspace_tx(session, workspace_id):
            await session.execute(
                text(
                    "INSERT INTO app.idempotency_keys"
                    " (workspace_id, key, operation, fingerprint, state, response_body_ct)"
                    " VALUES (app.current_workspace(), :key, :operation, :fp, :state, :body)"
                ),
                {
                    "key": secrets.token_hex(16),
                    "operation": operation,
                    "fp": os.urandom(32),
                    "state": state,
                    "body": body,
                },
            )

    assert sqlstate(error.value) == CHECK_VIOLATION


async def test_db07_workspace_create_key_replays_the_created_workspace(
    sessions: Sessions,
) -> None:
    params = {"key": os.urandom(32), "fingerprint": os.urandom(32)}
    workspace_id, body = uuid.uuid4(), os.urandom(80)

    async with sessions.app() as session, session.begin():
        first = (await session.execute(CLAIM_CREATE, params)).one()
        concurrent_retry = (await session.execute(CLAIM_CREATE, params)).one()
    async with sessions.app() as session, workspace_tx(session, workspace_id):
        await session.execute(
            text("SELECT app.create_workspace(:dek, 'kek-1', '2026-11-10', :evidence)"),
            {"dek": os.urandom(64), "evidence": os.urandom(32)},
        )
        completed = (
            await session.execute(
                text("SELECT app.complete_workspace_create_key(:key, 201, :body)"),
                {"key": params["key"], "body": body},
            )
        ).scalar()
    async with sessions.app() as session, session.begin():
        replay = (await session.execute(CLAIM_CREATE, params)).one()
        released_completed = (
            await session.execute(
                text("SELECT app.release_workspace_create_key(:key)"), {"key": params["key"]}
            )
        ).scalar()

    assert (first.is_new, first.state) == (True, "in_progress")
    assert (concurrent_retry.is_new, concurrent_retry.state) == (False, "in_progress")
    assert completed is True
    assert tuple(replay) == (False, "completed", params["fingerprint"], 201, workspace_id, body)
    assert released_completed is False


async def test_db07_expired_workspace_create_keys_are_purged_by_the_worker(
    sessions: Sessions,
) -> None:
    params = {"key": os.urandom(32), "fingerprint": os.urandom(32)}
    async with sessions.app() as session, session.begin():
        await session.execute(CLAIM_CREATE, params)
    async with sessions.superuser() as session, session.begin():
        await session.execute(
            text(
                "UPDATE app.workspace_create_keys SET expires_at = now() - interval '1 second'"
                " WHERE key_sha256 = :key"
            ),
            params,
        )

    async with sessions.worker() as session, session.begin():
        purged = (
            await session.execute(text("SELECT app.purge_expired_workspace_create_keys(500)"))
        ).scalar()
    async with sessions.app() as session, session.begin():
        reclaimed = (await session.execute(CLAIM_CREATE, params)).one()

    assert purged is not None
    assert purged >= 1
    assert reclaimed.is_new is True
