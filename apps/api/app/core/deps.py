"""Request dependencies: database session, authenticated session, scopes, workspace keys."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import Kek, WorkspaceKeys
from app.core.errors import ErrorCode, ProblemError
from app.core.security import CSRF_HEADER, SESSION_COOKIE, csrf_valid, session_token_sha256
from app.db.models import Workspace
from app.db.transaction import workspace_tx

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_RESOLVE_SESSION = text("SELECT session_id, workspace_id FROM app.resolve_session(:token_sha256)")


class Scope(StrEnum):
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    EXPORTS_CREATE = "exports:create"
    WORKSPACE_MANAGE = "workspace:manage"


# The owner's browser session gets every scope; narrower sessions come with share links.
OWNER_SCOPES = frozenset(Scope)


@dataclass(frozen=True, slots=True)
class SessionContext:
    session_id: UUID
    workspace_id: UUID
    scopes: frozenset[Scope]
    request_id: str


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """One AsyncSession per request; transactions are explicit (autobegin is off)."""
    async with request.app.state.db_sessions() as session:
        yield session


Db = Annotated[AsyncSession, Depends(get_db)]


async def get_session(request: Request, db: Db) -> SessionContext:
    """Authenticated session from `__Host-ma_sid`; 401 `unauthenticated` otherwise.

    Every state-changing method also needs a valid `X-CSRF-Token` (403 `csrf_failed`). The two
    anonymous operations, POST /workspaces and POST /sessions, do not use this dependency.
    """
    cookie = request.cookies.get(SESSION_COOKIE)
    token_sha256 = session_token_sha256(cookie) if cookie else None
    if token_sha256 is None:
        raise ProblemError(ErrorCode.UNAUTHENTICATED)
    async with db.begin():
        row = (await db.execute(_RESOLVE_SESSION, {"token_sha256": token_sha256})).one_or_none()
    if row is None:
        raise ProblemError(ErrorCode.UNAUTHENTICATED)
    session = SessionContext(
        session_id=row.session_id,
        workspace_id=row.workspace_id,
        scopes=OWNER_SCOPES,
        request_id=request.state.request_id,
    )
    secret = request.app.state.settings.csrf_secret.get_secret_value()
    if request.method not in _SAFE_METHODS and not csrf_valid(
        secret, session.session_id, request.headers.get(CSRF_HEADER)
    ):
        raise ProblemError(ErrorCode.CSRF_FAILED)
    return session


def require_scope(scope: Scope) -> Callable[..., Awaitable[SessionContext]]:
    """`session: Annotated[SessionContext, Depends(require_scope(Scope.DOCUMENTS_READ))]`."""

    async def dependency(
        session: Annotated[SessionContext, Depends(get_session)],
    ) -> SessionContext:
        if scope not in session.scopes:
            raise ProblemError(ErrorCode.SCOPE_INSUFFICIENT)
        return session

    return dependency


def session_tx(db: AsyncSession, session: SessionContext) -> AbstractAsyncContextManager[None]:
    """`workspace_tx` for the current session: RLS context plus audit session and request ids."""
    return workspace_tx(
        db, session.workspace_id, session_id=session.session_id, request_id=session.request_id
    )


def get_kek(request: Request) -> Kek:
    kek: Kek = request.app.state.kek
    return kek


async def load_workspace_keys(db: AsyncSession, kek: Kek, workspace_id: UUID) -> WorkspaceKeys:
    """Open this workspace's keys for the current request only. Call inside `workspace_tx`.

    A workspace that is crypto-erased (deleted) has no keys: such sessions are already revoked,
    so this is reached only in a race with deletion and answers 401. Opening the bundle is
    CPU-bound Tink work: keep it off the event loop so 50 VU of list/search still share I/O.
    """
    wrapped = await db.scalar(select(Workspace.dek_ciphertext).where(Workspace.id == workspace_id))
    if wrapped is None:
        raise ProblemError(ErrorCode.UNAUTHENTICATED)
    return await asyncio.to_thread(kek.open_workspace_keys, wrapped, workspace_id)
