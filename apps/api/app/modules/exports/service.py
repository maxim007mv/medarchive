"""Exports: fix the set of documents now, stream it as a ZIP within the hour (BE-11)."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from zipstream import ZipStream

from app.core.crypto import WorkspaceKeys
from app.core.deps import SessionContext, session_tx
from app.core.errors import ErrorCode, FieldError, ProblemError
from app.core.ids import new_id
from app.modules.documents import queries as documents
from app.modules.documents.filenames import pdf_file_name, unique_names
from app.modules.documents.files import iter_plaintext
from app.modules.documents.listing import ListFilter, build_filter
from app.modules.documents.repository import ListedDocument
from app.modules.exports import repository
from app.modules.exports.manifest import ManifestEntry, build_csv, build_json
from app.modules.exports.schemas import MAX_EXPORT_DOCUMENTS, Export, ExportCreate
from app.storage.s3 import ObjectStorage

NOTHING_TO_EXPORT = "Нет документов для экспорта"
DOCUMENTS_FOLDER = "documents"


@dataclass(frozen=True)
class Archive:
    file_name: str
    size_bytes: int
    chunks: Iterator[bytes]


async def create_export(
    db: AsyncSession, session: SessionContext, keys: WorkspaceKeys, body: ExportCreate, *, tz: str
) -> Export:
    selected = await _select(db, session, keys, body, tz)
    if not selected:
        raise ProblemError(ErrorCode.VALIDATION_ERROR, detail=NOTHING_TO_EXPORT)
    if len(selected) > MAX_EXPORT_DOCUMENTS:
        raise ProblemError(ErrorCode.VALIDATION_ERROR, errors=[FieldError("/scope")])
    export_id = new_id()
    total_bytes = sum(document.size_bytes for document in selected)
    async with session_tx(db, session):
        expires_at = await repository.insert_export(
            db,
            session.workspace_id,
            export_id=export_id,
            scope=body.scope,
            filter=body.filter.model_dump(mode="json", by_alias=True, exclude_none=True)
            if body.filter
            else {},
            document_ids=[document.id for document in selected],
            total_bytes=total_bytes,
        )
        await repository.audit(db, session.workspace_id, session, "export.create", export_id)
    return Export(
        id=export_id,
        scope=body.scope,
        document_count=len(selected),
        total_bytes=total_bytes,
        content_url=f"/api/v1/exports/{export_id}/content",
        expires_at=expires_at,
    )


async def _select(
    db: AsyncSession, session: SessionContext, keys: WorkspaceKeys, body: ExportCreate, tz: str
) -> list[ListedDocument]:
    if body.scope == "selected":
        if not body.document_ids:
            raise ProblemError(ErrorCode.VALIDATION_ERROR, errors=[FieldError("/document_ids")])
        return await documents.get_selected(db, session, body.document_ids)
    list_filter = ListFilter()
    if body.scope == "filtered" and body.filter:
        list_filter = build_filter(
            q=body.filter.q,
            types=list(body.filter.type or ()),
            date_field=body.filter.date_field or "document",
            date_from=body.filter.date_from,
            date_to=body.filter.date_to,
            undated=bool(body.filter.undated),
        )
    return await documents.find_matching(db, session, keys, list_filter=list_filter, tz=tz)


async def open_archive(
    db: AsyncSession,
    session: SessionContext,
    keys: WorkspaceKeys,
    storage: ObjectStorage,
    export_id: UUID,
    *,
    today: date,
) -> Archive:
    """The ZIP of a live export; an expired or unknown export is 404 `not_found`."""
    async with session_tx(db, session):
        document_ids = await repository.get_live_export(db, session.workspace_id, export_id)
        if document_ids is None:
            raise ProblemError(ErrorCode.NOT_FOUND)
        await repository.audit(db, session.workspace_id, session, "export.download", export_id)
    items = await documents.get_export_items(db, session, keys, document_ids)
    names = unique_names(pdf_file_name(item.title, item.document_date) for item in items)
    entries = [
        ManifestEntry(
            title=item.title,
            type_code=item.type_code,
            type_title=item.type_title,
            document_date=item.document_date,
            uploaded_at=item.uploaded_at,
            note=item.note,
            file_name=name,
            size_bytes=item.size_bytes,
            sha256=item.sha256,
        )
        for item, name in zip(items, names, strict=True)
    ]
    # Stored, not deflated: PDFs are compressed already, and a sized stream gives Content-Length.
    archive = ZipStream(sized=True)
    for item, entry in zip(items, entries, strict=True):
        archive.add(
            iter_plaintext(storage, keys, object_key=item.object_key, document_id=item.id),
            f"{DOCUMENTS_FOLDER}/{entry.file_name}",
            size=item.size_bytes,
        )
    archive.add(build_csv(entries), "documents.csv")
    archive.add(build_json(entries), "documents.json")
    return Archive(
        file_name=f"medarchive_{today.isoformat()}.zip",
        size_bytes=len(archive),
        chunks=iter(archive),
    )
