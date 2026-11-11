"""Request dependencies shared by the uploads, documents and exports routers."""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Request
from sqlalchemy import select

from app.core.crypto import Kek, WorkspaceKeys
from app.core.deps import Db, SessionContext, get_kek, get_session, session_tx
from app.core.errors import ErrorCode, ProblemError
from app.core.page_token import PageTokenCodec
from app.db.models import Workspace
from app.modules.auth.schemas import DEFAULT_TIMEZONE
from app.storage.s3 import ObjectStorage


def get_storage(request: Request) -> ObjectStorage:
    storage: ObjectStorage = request.app.state.storage
    return storage


def get_page_tokens(request: Request) -> PageTokenCodec:
    codec: PageTokenCodec = request.app.state.page_tokens
    return codec


@dataclass(frozen=True, slots=True)
class WorkspaceRow:
    dek_ciphertext: bytes | None
    timezone: str | None


async def get_workspace_row(
    db: Db, session: Annotated[SessionContext, Depends(get_session)]
) -> WorkspaceRow:
    """Wrapped keys and zone in one transaction; FastAPI reuses it for Keys and UserTimezone."""
    async with session_tx(db, session):
        row = (
            await db.execute(
                select(Workspace.dek_ciphertext, Workspace.timezone).where(
                    Workspace.id == session.workspace_id
                )
            )
        ).one_or_none()
    if row is None:
        return WorkspaceRow(None, None)
    return WorkspaceRow(row.dek_ciphertext, row.timezone)


async def get_workspace_keys(
    workspace: Annotated[WorkspaceRow, Depends(get_workspace_row)],
    session: Annotated[SessionContext, Depends(get_session)],
    kek: Annotated[Kek, Depends(get_kek)],
) -> WorkspaceKeys:
    """Keys for this request only. A crypto-erased (deleted) workspace has none: such sessions
    are already revoked, so this is reached only in a race with deletion and answers 401.
    Opening the bundle is CPU-bound Tink work, kept off the event loop.
    """
    if workspace.dek_ciphertext is None:
        raise ProblemError(ErrorCode.UNAUTHENTICATED)
    return await asyncio.to_thread(
        kek.open_workspace_keys, workspace.dek_ciphertext, session.workspace_id
    )


async def get_user_timezone(
    workspace: Annotated[WorkspaceRow, Depends(get_workspace_row)],
) -> str:
    """The archive's IANA zone from POST /workspaces; older archives without one use Moscow."""
    return workspace.timezone or DEFAULT_TIMEZONE


def today_in(tz: str) -> date:
    return datetime.now(ZoneInfo(tz)).date()


Storage = Annotated[ObjectStorage, Depends(get_storage)]
Keys = Annotated[WorkspaceKeys, Depends(get_workspace_keys)]
PageTokens = Annotated[PageTokenCodec, Depends(get_page_tokens)]
UserTimezone = Annotated[str, Depends(get_user_timezone)]
