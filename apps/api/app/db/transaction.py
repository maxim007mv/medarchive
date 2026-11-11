from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# is_local = true: the values end with the transaction, so a pooled connection (or PgBouncer in
# transaction mode) never carries one workspace into the next request (DB-04).
_SET_CONTEXT = text(
    "SELECT set_config('app.workspace_id', :workspace_id, true),"
    " set_config('app.session_id', :session_id, true),"
    " set_config('app.request_id', :request_id, true)"
)


@asynccontextmanager
async def workspace_tx(
    session: AsyncSession,
    workspace_id: UUID,
    *,
    session_id: UUID | None = None,
    request_id: str | None = None,
) -> AsyncIterator[None]:
    """Run one transaction under RLS for `workspace_id`; commits on exit, rolls back on error.

    The context is the first statement of the transaction. `session_id` and `request_id` go to
    the audit trigger.
    """
    if session.in_transaction():
        raise RuntimeError("workspace_tx must open the transaction itself")
    async with session.begin():
        await session.execute(
            _SET_CONTEXT,
            {
                "workspace_id": str(workspace_id),
                "session_id": str(session_id) if session_id else "",
                "request_id": request_id or "",
            },
        )
        yield
