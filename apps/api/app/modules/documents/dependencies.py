"""Request dependencies shared by the uploads, documents and exports routers."""

from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Request

from app.core.crypto import Kek, WorkspaceKeys
from app.core.deps import Db, SessionContext, get_kek, get_session, load_workspace_keys, session_tx
from app.core.page_token import PageTokenCodec
from app.modules.auth.repository import workspace_timezone
from app.modules.auth.schemas import DEFAULT_TIMEZONE
from app.storage.s3 import ObjectStorage


def get_storage(request: Request) -> ObjectStorage:
    storage: ObjectStorage = request.app.state.storage
    return storage


def get_page_tokens(request: Request) -> PageTokenCodec:
    codec: PageTokenCodec = request.app.state.page_tokens
    return codec


async def get_workspace_keys(
    db: Db,
    session: Annotated[SessionContext, Depends(get_session)],
    kek: Annotated[Kek, Depends(get_kek)],
) -> WorkspaceKeys:
    async with session_tx(db, session):
        return await load_workspace_keys(db, kek, session.workspace_id)


async def get_user_timezone(
    db: Db, session: Annotated[SessionContext, Depends(get_session)]
) -> str:
    """The archive's IANA zone from POST /workspaces; older archives without one use Moscow."""
    async with session_tx(db, session):
        timezone = await workspace_timezone(db, session.workspace_id)
    return timezone or DEFAULT_TIMEZONE


def today_in(tz: str) -> date:
    return datetime.now(ZoneInfo(tz)).date()


Storage = Annotated[ObjectStorage, Depends(get_storage)]
Keys = Annotated[WorkspaceKeys, Depends(get_workspace_keys)]
PageTokens = Annotated[PageTokenCodec, Depends(get_page_tokens)]
UserTimezone = Annotated[str, Depends(get_user_timezone)]
