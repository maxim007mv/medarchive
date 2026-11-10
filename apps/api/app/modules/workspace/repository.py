from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Consent, Document, DocumentFile, DocumentType, Workspace
from app.modules.workspace.schemas import ConsentOut, DocumentTypeOut, WorkspaceOut


async def workspace_summary(db: AsyncSession, workspace_id: UUID) -> WorkspaceOut | None:
    """Inside workspace_tx. Deleted documents are invisible under RLS (`hide_deleted`)."""
    live_documents = select(func.count()).where(Document.workspace_id == workspace_id)
    total_bytes = (
        select(func.coalesce(func.sum(DocumentFile.size_bytes), 0))
        .join(
            Document,
            and_(
                Document.id == DocumentFile.document_id,
                Document.workspace_id == DocumentFile.workspace_id,
            ),
        )
        .where(DocumentFile.workspace_id == workspace_id)
    )
    row = (
        await db.execute(
            select(
                Workspace.created_at,
                live_documents.scalar_subquery().label("document_count"),
                live_documents.where(Document.document_date.is_(None))
                .scalar_subquery()
                .label("undated_count"),
                total_bytes.scalar_subquery().label("total_bytes"),
                Consent.policy_version,
                Consent.accepted_at,
            )
            .outerjoin(
                Consent,
                and_(Consent.workspace_id == Workspace.id, Consent.withdrawn_at.is_(None)),
            )
            .where(Workspace.id == workspace_id, Workspace.deleted_at.is_(None))
        )
    ).one_or_none()
    if row is None:
        return None
    consent = (
        ConsentOut(policy_version=row.policy_version, accepted_at=row.accepted_at)
        if row.policy_version is not None
        else None
    )
    return WorkspaceOut(
        id=workspace_id,
        created_at=row.created_at,
        document_count=row.document_count,
        total_bytes=row.total_bytes,
        undated_count=row.undated_count,
        consent=consent,
    )


async def delete_workspace(db: AsyncSession) -> datetime | None:
    """Inside workspace_tx: mark deleted, erase the key bundle, revoke sessions, key and consent
    (ADR-041). Returns the purge deadline, None if already deleted."""
    purge_after: datetime | None = (
        await db.execute(text("SELECT app.delete_workspace()"))
    ).scalar_one()
    return purge_after


async def document_types(db: AsyncSession) -> list[DocumentTypeOut]:
    """Reference data shared by all workspaces (no RLS)."""
    rows = await db.execute(
        select(DocumentType.code, DocumentType.title_ru).order_by(DocumentType.sort_order)
    )
    return [DocumentTypeOut(code=row.code, title=row.title_ru) for row in rows]
