"""Archive creation, sign-in by access key and sessions (BE-04, BE-05)."""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import Kek, WorkspaceKeys
from app.core.deps import SessionContext, load_workspace_keys, session_tx
from app.core.errors import ErrorCode, ProblemError
from app.core.idempotency import IN_PROGRESS_RETRY_AFTER, request_fingerprint
from app.core.ids import new_id
from app.core.security import new_session_token
from app.db.transaction import workspace_tx
from app.modules.auth import repository
from app.modules.auth.access_key import (
    AccessKey,
    generate_access_key,
    hash_secret,
    parse_access_key,
    verify_secret,
)
from app.modules.auth.consent import EVIDENCE_SHA256, POLICY_VERSION
from app.modules.auth.repository import IpPrefix
from app.modules.auth.schemas import DEFAULT_TIMEZONE, WorkspaceBrief, WorkspaceCreate

WORKSPACE_CREATED_STATUS = 201
ACCESS_KEY_ATTEMPTS = 3


@dataclass(frozen=True, slots=True)
class IssuedSession:
    workspace_id: UUID
    session_id: UUID
    cookie: str
    idle_expires_at: datetime
    timezone: str


@dataclass(frozen=True, slots=True)
class SessionState:
    idle_expires_at: datetime
    timezone: str


@dataclass(frozen=True, slots=True)
class CreatedWorkspace:
    """`body` is `{workspace, access_key}`; the session part is added per response."""

    body: dict[str, Any]
    session: IssuedSession
    replayed: bool


@dataclass(frozen=True, slots=True)
class RequestMeta:
    request_id: str
    ip_prefix: IpPrefix | None


async def create_workspace(
    db: AsyncSession, kek: Kek, *, key: str, payload: WorkspaceCreate, meta: RequestMeta
) -> CreatedWorkspace:
    """Create archive, consent, access key and session; a repeated key replays (ADR-045).

    The replay returns the same archive and access key with a new session: the first session
    token exists only as a hash.
    """
    key_sha256 = hashlib.sha256(key.encode()).digest()
    fingerprint = request_fingerprint(payload)
    async with db.begin():
        claim = await repository.claim_workspace_create_key(db, key_sha256, fingerprint)
    if not claim.is_new:
        return await _replay_creation(db, kek, claim, key_sha256, fingerprint, meta)
    try:
        return await _create(db, kek, key_sha256, payload.timezone, meta)
    except Exception:
        async with db.begin():
            await repository.release_workspace_create_key(db, key_sha256)
        raise


async def _create(
    db: AsyncSession, kek: Kek, key_sha256: bytes, timezone: str, meta: RequestMeta
) -> CreatedWorkspace:
    workspace_id = new_id()
    keys, wrapped = kek.new_workspace_keys(workspace_id)
    cookie, token_sha256 = new_session_token()
    async with workspace_tx(db, workspace_id, request_id=meta.request_id):
        created_at = await repository.create_workspace(
            db,
            dek_ciphertext=wrapped,
            kek_key_id=kek.key_id,
            policy_version=POLICY_VERSION,
            evidence_sha256=EVIDENCE_SHA256,
            timezone=timezone,
        )
        access_key, _ = await issue_new_access_key(db)
        session = await _start_session(
            db, workspace_id, cookie, token_sha256, "session.create", meta
        )
        for action in ("workspace.create", "consent.accept", "access_key.issue"):
            await repository.add_audit(
                db,
                workspace_id,
                action,
                session_id=session.session_id,
                request_id=meta.request_id,
                ip_prefix=meta.ip_prefix,
            )
        body = {
            "workspace": WorkspaceBrief(
                id=workspace_id, created_at=created_at, document_count=0
            ).model_dump(mode="json"),
            "access_key": access_key.display,
        }
        await repository.complete_workspace_create_key(
            db, key_sha256, WORKSPACE_CREATED_STATUS, _seal(keys, body, workspace_id, key_sha256)
        )
    return CreatedWorkspace(body, session, replayed=False)


async def _replay_creation(
    db: AsyncSession,
    kek: Kek,
    claim: repository.CreateKeyClaim,
    key_sha256: bytes,
    fingerprint: bytes,
    meta: RequestMeta,
) -> CreatedWorkspace:
    if claim.fingerprint != fingerprint:
        raise ProblemError(ErrorCode.IDEMPOTENCY_KEY_REUSED)
    if claim.state != "completed" or claim.workspace_id is None or claim.response_body_ct is None:
        raise ProblemError(
            ErrorCode.IDEMPOTENCY_IN_PROGRESS, headers={"Retry-After": IN_PROGRESS_RETRY_AFTER}
        )
    workspace_id = claim.workspace_id
    cookie, token_sha256 = new_session_token()
    async with workspace_tx(db, workspace_id, request_id=meta.request_id):
        keys = await load_workspace_keys(db, kek, workspace_id)
        session = await _start_session(
            db, workspace_id, cookie, token_sha256, "session.create", meta
        )
    body = json.loads(keys.decrypt_field(claim.response_body_ct, _aad(workspace_id, key_sha256)))
    return CreatedWorkspace(body, session, replayed=True)


async def issue_new_access_key(db: AsyncSession) -> tuple[AccessKey, bool]:
    """Inside workspace_tx: a fresh key replaces the active one; True if one was revoked.

    The 6-character lookup id is random, so it can hit an existing one; then a new key is drawn.
    """
    for _ in range(ACCESS_KEY_ATTEMPTS):
        access_key = generate_access_key()
        secret_hash = await asyncio.to_thread(hash_secret, access_key.secret)
        try:
            revoked_previous = await repository.issue_access_key(
                db, access_key.lookup_id, secret_hash
            )
        except repository.LookupIdTakenError:
            continue
        if revoked_previous is None:
            raise ProblemError(ErrorCode.UNAUTHENTICATED)
        return access_key, revoked_previous
    raise RuntimeError(f"no free access key lookup id in {ACCESS_KEY_ATTEMPTS} attempts")


async def open_by_access_key(db: AsyncSession, typed_key: str, meta: RequestMeta) -> IssuedSession:
    """New session for the archive of a valid key; 401 `access_key_invalid` otherwise.

    The Argon2id check runs for every attempt, also for malformed keys and unknown lookup ids,
    so the answer time does not reveal whether an archive exists.
    """
    access_key = parse_access_key(typed_key)
    found = None
    if access_key is not None:
        async with db.begin():
            found = await repository.find_access_key(db, access_key.lookup_id)
    secret = access_key.secret if access_key else typed_key
    valid = await asyncio.to_thread(verify_secret, found.secret_hash if found else None, secret)
    if found is None:
        raise ProblemError(ErrorCode.ACCESS_KEY_INVALID)
    if not valid:
        async with workspace_tx(db, found.workspace_id, request_id=meta.request_id):
            await repository.add_audit(
                db,
                found.workspace_id,
                "session.restore_failed",
                session_id=None,
                request_id=meta.request_id,
                ip_prefix=meta.ip_prefix,
            )
        raise ProblemError(ErrorCode.ACCESS_KEY_INVALID)
    cookie, token_sha256 = new_session_token()
    async with workspace_tx(db, found.workspace_id, request_id=meta.request_id):
        return await _start_session(
            db, found.workspace_id, cookie, token_sha256, "session.restore", meta
        )


async def refresh_session(db: AsyncSession, session: SessionContext) -> SessionState:
    """Extend the idle timeout of the current session; 401 if it expired meanwhile."""
    async with session_tx(db, session):
        idle_expires_at = await repository.touch_session(db, session.session_id)
        timezone = await repository.workspace_timezone(db, session.workspace_id)
    if idle_expires_at is None:
        raise ProblemError(ErrorCode.UNAUTHENTICATED)
    return SessionState(idle_expires_at, timezone or DEFAULT_TIMEZONE)


async def end_session(
    db: AsyncSession, session: SessionContext, ip_prefix: IpPrefix | None
) -> None:
    async with session_tx(db, session):
        await repository.revoke_session(db, session.session_id)
        await repository.add_audit(
            db,
            session.workspace_id,
            "session.revoke",
            session_id=session.session_id,
            request_id=session.request_id,
            ip_prefix=ip_prefix,
        )


async def _start_session(
    db: AsyncSession,
    workspace_id: UUID,
    cookie: str,
    token_sha256: bytes,
    action: str,
    meta: RequestMeta,
) -> IssuedSession:
    session = await repository.create_session(db, token_sha256)
    if session is None:
        raise ProblemError(ErrorCode.UNAUTHENTICATED)
    await repository.add_audit(
        db,
        workspace_id,
        action,
        session_id=session.session_id,
        request_id=meta.request_id,
        ip_prefix=meta.ip_prefix,
    )
    timezone = await repository.workspace_timezone(db, workspace_id)
    return IssuedSession(
        workspace_id,
        session.session_id,
        cookie,
        session.idle_expires_at,
        timezone or DEFAULT_TIMEZONE,
    )


def _aad(workspace_id: UUID, key_sha256: bytes) -> bytes:
    return workspace_id.bytes + key_sha256


def _seal(
    keys: WorkspaceKeys, body: dict[str, Any], workspace_id: UUID, key_sha256: bytes
) -> bytes:
    return keys.encrypt_field(json.dumps(body, ensure_ascii=False), _aad(workspace_id, key_sha256))
