"""uploads rows. Call inside `workspace_tx`; every query also filters by workspace_id."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Upload

UPLOAD_TTL = text("now() + interval '1 hour'")
_ENQUEUE_PURGE = text("SELECT app.enqueue_purge(:object_key, :reason)")


@dataclass(frozen=True)
class PendingUpload:
    id: UUID
    quarantine_key: str
    status: str
    reject_code: str | None
    is_expired: bool
    original_name_ct: bytes


def quarantine_key(workspace_id: UUID, upload_id: UUID) -> str:
    return f"q/{workspace_id}/{upload_id}.bin"


async def insert_upload(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    upload_id: UUID,
    max_bytes: int,
    original_name_ct: bytes,
) -> None:
    await db.execute(
        insert(Upload).values(
            id=upload_id,
            workspace_id=workspace_id,
            quarantine_key=quarantine_key(workspace_id, upload_id),
            max_bytes=max_bytes,
            original_name_ct=original_name_ct,
            expires_at=UPLOAD_TTL,
        )
    )


async def lock_upload(
    db: AsyncSession, workspace_id: UUID, upload_id: UUID
) -> PendingUpload | None:
    """The upload row, locked until the end of the transaction so only one document consumes it."""
    row = (
        await db.execute(
            select(
                Upload.id,
                Upload.quarantine_key,
                Upload.status,
                Upload.reject_code,
                (Upload.expires_at <= func.now()).label("is_expired"),
                Upload.original_name_ct,
            )
            .where(Upload.workspace_id == workspace_id, Upload.id == upload_id)
            .with_for_update()
        )
    ).one_or_none()
    # A row without a name cannot become a document (file.original_name is required).
    if row is None or row.original_name_ct is None:
        return None
    return PendingUpload(**row._asdict())


async def set_status(
    db: AsyncSession,
    workspace_id: UUID,
    upload_id: UUID,
    *,
    status: str,
    reject_code: str | None = None,
) -> None:
    await db.execute(
        update(Upload)
        .where(Upload.workspace_id == workspace_id, Upload.id == upload_id)
        .values(status=status, reject_code=reject_code)
    )


async def enqueue_purge(db: AsyncSession, object_key: str, reason: str) -> None:
    """Queue an object of the current workspace for deletion by the worker (ADR-044)."""
    await db.execute(_ENQUEUE_PURGE, {"object_key": object_key, "reason": reason})
