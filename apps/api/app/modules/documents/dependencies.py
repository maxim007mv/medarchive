"""Request dependencies shared by the uploads, documents and exports routers."""

from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Request

from app.core.crypto import Kek, WorkspaceKeys
from app.core.deps import Db, SessionContext, get_kek, get_session, load_workspace_keys, session_tx
from app.core.page_token import PageTokenCodec
from app.storage.s3 import ObjectStorage

# Until the session carries the user's zone (request to the core agent in
# docs/progress/backend-documents.md), dates are judged in the zone of the product's users.
DEFAULT_TIMEZONE = "Europe/Moscow"


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


def today_in(tz: str) -> date:
    return datetime.now(ZoneInfo(tz)).date()


Storage = Annotated[ObjectStorage, Depends(get_storage)]
Keys = Annotated[WorkspaceKeys, Depends(get_workspace_keys)]
PageTokens = Annotated[PageTokenCodec, Depends(get_page_tokens)]
