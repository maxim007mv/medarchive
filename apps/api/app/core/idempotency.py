"""Idempotency-Key for creating POSTs (06-api-contract, section 5; ADR-045).

A new key is claimed as `in_progress` in its own transaction, so a concurrent duplicate sees it
and gets 409. Only a 2xx answer is kept: status, headers and body encrypted with the workspace
key (AAD = workspace id + key) for 24 hours. Any error releases the claim and a retry runs anew.
`workspaces.create` has no workspace yet and uses its own table (modules/auth).
"""

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import WorkspaceKeys
from app.core.deps import SessionContext, session_tx
from app.core.errors import ErrorCode, FieldError, ProblemError
from app.db.models import IdempotencyKey

IDEMPOTENT_REPLAYED = "Idempotent-Replayed"
KEY_MIN_LENGTH = 16
KEY_MAX_LENGTH = 64
IN_PROGRESS_RETRY_AFTER = "1"


class Operation(StrEnum):
    UPLOADS_CREATE = "uploads.create"
    DOCUMENTS_CREATE = "documents.create"
    EXPORTS_CREATE = "exports.create"
    SUGGESTIONS_CREATE = "suggestions.create"
    WORKSPACE_ROTATE_KEY = "workspace.rotateKey"


@dataclass(frozen=True, slots=True)
class StoredResponse:
    """A successful answer as it is kept for replay."""

    status: int
    body: dict[str, Any]
    headers: Mapping[str, str] = field(default_factory=dict)
    resource_id: UUID | None = None
    # True when this is the saved answer of an earlier attempt.
    replayed: bool = False

    def to_response(self) -> JSONResponse:
        headers = dict(self.headers)
        if self.replayed:
            headers[IDEMPOTENT_REPLAYED] = "true"
        return JSONResponse(self.body, status_code=self.status, headers=headers)

    def seal(self, keys: WorkspaceKeys, aad: bytes) -> bytes:
        envelope = {"status": self.status, "headers": dict(self.headers), "body": self.body}
        return keys.encrypt_field(json.dumps(envelope, ensure_ascii=False), aad)

    @classmethod
    def unseal(cls, keys: WorkspaceKeys, ciphertext: bytes, aad: bytes) -> "StoredResponse":
        envelope = json.loads(keys.decrypt_field(ciphertext, aad))
        return cls(
            status=envelope["status"],
            body=envelope["body"],
            headers=envelope["headers"],
            replayed=True,
        )


def require_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    """Route dependency: 400 `idempotency_key_missing` without the header."""
    if not idempotency_key:
        raise ProblemError(ErrorCode.IDEMPOTENCY_KEY_MISSING)
    if not KEY_MIN_LENGTH <= len(idempotency_key) <= KEY_MAX_LENGTH:
        raise ProblemError(ErrorCode.VALIDATION_ERROR, errors=[FieldError("/Idempotency-Key")])
    return idempotency_key


def request_fingerprint(payload: BaseModel | None) -> bytes:
    """SHA-256 of the validated body in canonical JSON: formatting differences do not count."""
    canonical = (
        ""
        if payload is None
        else json.dumps(
            payload.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
    return hashlib.sha256(canonical.encode()).digest()


def body_aad(workspace_id: UUID, key: str) -> bytes:
    return workspace_id.bytes + key.encode()


async def run_idempotent(
    db: AsyncSession,
    session: SessionContext,
    keys: WorkspaceKeys,
    *,
    operation: Operation,
    key: str,
    payload: BaseModel | None,
    execute: Callable[[], Awaitable[StoredResponse]],
) -> StoredResponse:
    """Run `execute` at most once per key; repeats get the first answer back (`replayed`).

    `execute` opens its own transactions. Errors it raises (ProblemError included) propagate
    after the claim is released.
    """
    fingerprint = request_fingerprint(payload)
    stored = await _claim(db, session, operation=operation, key=key, fingerprint=fingerprint)
    if stored is not None:
        return StoredResponse.unseal(keys, stored, body_aad(session.workspace_id, key))
    try:
        result = await execute()
    except Exception:
        await _release(db, session, key)
        raise
    async with session_tx(db, session):
        await db.execute(
            update(IdempotencyKey)
            .where(IdempotencyKey.workspace_id == session.workspace_id, IdempotencyKey.key == key)
            .values(
                state="completed",
                response_status=result.status,
                resource_id=result.resource_id,
                response_body_ct=result.seal(keys, body_aad(session.workspace_id, key)),
            )
        )
    return result


async def _claim(
    db: AsyncSession, session: SessionContext, *, operation: Operation, key: str, fingerprint: bytes
) -> bytes | None:
    """Claim a new key (None) or return the sealed answer of a completed one."""
    async with session_tx(db, session):
        # An expired row the worker has not purged yet must not block or replay.
        await db.execute(
            delete(IdempotencyKey).where(
                IdempotencyKey.workspace_id == session.workspace_id,
                IdempotencyKey.key == key,
                IdempotencyKey.expires_at <= func.now(),
            )
        )
        claimed = await db.scalar(
            insert(IdempotencyKey)
            .values(
                workspace_id=session.workspace_id,
                key=key,
                operation=operation.value,
                fingerprint=fingerprint,
            )
            .on_conflict_do_nothing()
            .returning(IdempotencyKey.key)
        )
        if claimed is not None:
            return None
        existing = (
            await db.execute(
                select(
                    IdempotencyKey.operation,
                    IdempotencyKey.fingerprint,
                    IdempotencyKey.state,
                    IdempotencyKey.response_body_ct,
                ).where(
                    IdempotencyKey.workspace_id == session.workspace_id,
                    IdempotencyKey.key == key,
                )
            )
        ).one()
    if existing.operation != operation.value or existing.fingerprint != fingerprint:
        raise ProblemError(ErrorCode.IDEMPOTENCY_KEY_REUSED)
    if existing.state != "completed" or existing.response_body_ct is None:
        raise ProblemError(
            ErrorCode.IDEMPOTENCY_IN_PROGRESS, headers={"Retry-After": IN_PROGRESS_RETRY_AFTER}
        )
    sealed: bytes = existing.response_body_ct
    return sealed


async def _release(db: AsyncSession, session: SessionContext, key: str) -> None:
    async with session_tx(db, session):
        await db.execute(
            delete(IdempotencyKey).where(
                IdempotencyKey.workspace_id == session.workspace_id,
                IdempotencyKey.key == key,
                IdempotencyKey.state == "in_progress",
            )
        )
