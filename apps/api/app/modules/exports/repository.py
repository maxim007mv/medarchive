"""exports rows and their audit entries. Call inside `workspace_tx`."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SessionContext
from app.db.models import Export

# Plain INSERT: the roles have no SELECT on the journal, so no RETURNING of the identity key.
_INSERT_AUDIT = text(
    "INSERT INTO app.audit_log (workspace_id, session_id, action, entity_id, request_id)"
    " VALUES (:workspace_id, :session_id, :action, :entity_id, :request_id)"
)


async def insert_export(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    export_id: UUID,
    scope: str,
    filter: dict[str, Any],
    document_ids: list[UUID],
    total_bytes: int,
) -> datetime:
    """Returns `expires_at`, one hour from now by the column default."""
    expires_at: datetime = (
        await db.execute(
            insert(Export)
            .values(
                id=export_id,
                workspace_id=workspace_id,
                scope=scope,
                filter=filter,
                document_ids=document_ids,
                total_bytes=total_bytes,
            )
            .returning(Export.expires_at)
        )
    ).scalar_one()
    return expires_at


async def get_live_export(
    db: AsyncSession, workspace_id: UUID, export_id: UUID
) -> list[UUID] | None:
    """Document ids of an export that has not expired yet."""
    document_ids: list[UUID] | None = await db.scalar(
        select(Export.document_ids).where(
            Export.workspace_id == workspace_id,
            Export.id == export_id,
            Export.expires_at > func.now(),
        )
    )
    return document_ids


async def audit(
    db: AsyncSession, workspace_id: UUID, session: SessionContext, action: str, entity_id: UUID
) -> None:
    """Only the action and the export id: the journal never holds document data."""
    await db.execute(
        _INSERT_AUDIT,
        {
            "workspace_id": workspace_id,
            "session_id": session.session_id,
            "action": action,
            "entity_id": entity_id,
            "request_id": session.request_id,
        },
    )
