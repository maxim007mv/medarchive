"""Documents: create from an upload, card, list, edit, delete (BE-06..BE-10).

Titles, notes and file names are encrypted with the workspace field key, AAD = document id, so
a ciphertext copied into another row does not decrypt. Plaintext never reaches logs or errors.
"""

import asyncio
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import WorkspaceKeys
from app.core.deps import SessionContext, session_tx
from app.core.errors import ErrorCode, FieldError, ProblemError
from app.core.ids import new_id
from app.modules.documents import repository
from app.modules.documents.content import ByteRange, parse_range
from app.modules.documents.files import StoredFile, open_plaintext, store_verified_pdf
from app.modules.documents.repository import NewDocument
from app.modules.documents.schemas import (
    Document,
    DocumentCreate,
    DocumentPatch,
    FileInfo,
)
from app.modules.uploads import repository as uploads
from app.modules.uploads.pdf import PdfRejectedError
from app.modules.uploads.schemas import MAX_UPLOAD_BYTES
from app.modules.uploads.service import original_name_aad
from app.storage.s3 import ObjectStorage, StorageUnavailableError


def etag(version: int) -> str:
    return f'"v{version}"'


def etag_matches(header: str, version: int) -> bool:
    """`If-Match` / `If-None-Match`: a list of strong tags or `*`."""
    tags = {tag.strip() for tag in header.split(",")}
    return "*" in tags or etag(version) in tags


@dataclass(frozen=True)
class Download:
    """A decrypted file stream; `byte_range` is None when the whole file is sent."""

    title: str
    document_date: date | None
    size_bytes: int
    byte_range: ByteRange | None
    chunks: Iterator[bytes]


async def create_document(
    db: AsyncSession,
    session: SessionContext,
    keys: WorkspaceKeys,
    storage: ObjectStorage,
    body: DocumentCreate,
    *,
    today: date,
) -> Document:
    """Verify the quarantined PDF, store its ciphertext, then write all rows in one transaction.

    A file written to ma-docs whose transaction then fails is removed by the purge worker
    (orphan objects older than one hour, 05-architecture, 5.1).
    """
    _check_not_future(body.document_date, today)
    workspace_id = session.workspace_id
    async with session_tx(db, session):
        if not await repository.has_active_consent(db, workspace_id):
            raise ProblemError(ErrorCode.CONSENT_REQUIRED)
        upload = await _usable_upload(db, workspace_id, body.upload_id)
    document_id = new_id()
    object_key = repository.object_key(workspace_id, document_id)
    stored = await _store_upload(db, session, keys, storage, upload, document_id)

    original_name = keys.decrypt_field(upload.original_name_ct, original_name_aad(body.upload_id))
    aad = document_id.bytes
    async with session_tx(db, session):
        # Re-check under the lock: a concurrent request may have consumed the upload meanwhile.
        await _usable_upload(db, workspace_id, body.upload_id)
        uploaded_at, updated_at, version = await repository.insert_document(
            db,
            workspace_id,
            NewDocument(
                id=document_id,
                type_code=body.type,
                title_ct=keys.encrypt_field(body.title, aad),
                title_bidx=keys.title_bidx(body.title),
                note_ct=keys.encrypt_field(body.note, aad) if body.note else None,
                document_date=body.document_date,
                object_key=object_key,
                size_bytes=stored.size_bytes,
                sha256=stored.sha256,
                page_count=stored.page_count,
                original_name_ct=keys.encrypt_field(original_name, aad),
            ),
        )
        await uploads.set_status(db, workspace_id, body.upload_id, status="consumed")
        await uploads.enqueue_purge(db, upload.quarantine_key, "orphan")
    # The plaintext copy should not wait for the worker; if storage fails now, the queued purge
    # retries, and failing the request would only make the client resend a consumed upload.
    with suppress(StorageUnavailableError):
        await asyncio.to_thread(storage.quarantine.delete, upload.quarantine_key)
    return Document(
        id=document_id,
        title=body.title,
        type=body.type,
        document_date=body.document_date,
        uploaded_at=uploaded_at,
        updated_at=updated_at,
        note=body.note,
        file=FileInfo(
            original_name=original_name,
            size_bytes=stored.size_bytes,
            page_count=stored.page_count,
        ),
        version=version,
    )


async def _store_upload(
    db: AsyncSession,
    session: SessionContext,
    keys: WorkspaceKeys,
    storage: ObjectStorage,
    upload: uploads.PendingUpload,
    document_id: UUID,
) -> StoredFile:
    """Check the quarantined object and write its ciphertext; a bad PDF rejects the upload."""
    size_bytes = await asyncio.to_thread(storage.quarantine.size, upload.quarantine_key)
    if size_bytes is None:
        raise ProblemError(ErrorCode.UPLOAD_INCOMPLETE)
    if size_bytes > MAX_UPLOAD_BYTES:
        raise ProblemError(ErrorCode.FILE_TOO_LARGE)
    try:
        return await asyncio.to_thread(
            store_verified_pdf,
            storage,
            keys,
            quarantine_key=upload.quarantine_key,
            object_key=repository.object_key(session.workspace_id, document_id),
            document_id=document_id,
        )
    except PdfRejectedError as exc:
        async with session_tx(db, session):
            await uploads.set_status(
                db, session.workspace_id, upload.id, status="rejected", reject_code=exc.code
            )
            await uploads.enqueue_purge(db, upload.quarantine_key, "upload_rejected")
        raise ProblemError(ErrorCode(exc.code)) from None


async def _usable_upload(
    db: AsyncSession, workspace_id: UUID, upload_id: UUID
) -> uploads.PendingUpload:
    upload = await uploads.lock_upload(db, workspace_id, upload_id)
    if upload is None or upload.status == "consumed":
        raise ProblemError(ErrorCode.UPLOAD_NOT_FOUND)
    if upload.status == "rejected" and upload.reject_code:
        raise ProblemError(ErrorCode(upload.reject_code))
    if upload.is_expired or upload.status == "expired":
        raise ProblemError(ErrorCode.UPLOAD_EXPIRED)
    return upload


def _check_not_future(document_date: date | None, today: date) -> None:
    if document_date is not None and document_date > today:
        raise ProblemError(
            ErrorCode.DATE_IN_FUTURE,
            errors=[FieldError("/document_date", ErrorCode.DATE_IN_FUTURE)],
        )


async def get_document(
    db: AsyncSession, session: SessionContext, keys: WorkspaceKeys, document_id: UUID
) -> Document:
    async with session_tx(db, session):
        stored = await repository.get_document(db, session.workspace_id, document_id)
    if stored is None:
        raise ProblemError(ErrorCode.NOT_FOUND)
    return _to_document(stored, keys)


async def update_document(
    db: AsyncSession,
    session: SessionContext,
    keys: WorkspaceKeys,
    document_id: UUID,
    patch: DocumentPatch,
    *,
    if_match: str,
    today: date,
) -> Document:
    changes = patch.changes()
    _check_not_future(changes.get("document_date"), today)
    aad = document_id.bytes
    values: dict[str, Any] = {}
    if "title" in changes:
        values["title_ct"] = keys.encrypt_field(changes["title"], aad)
        values["title_bidx"] = keys.title_bidx(changes["title"])
    if "type" in changes:
        values["type_code"] = changes["type"]
    if "document_date" in changes:
        values["document_date"] = changes["document_date"]
    if "note" in changes:
        values["note_ct"] = keys.encrypt_field(changes["note"], aad) if changes["note"] else None
    async with session_tx(db, session):
        stored = await _locked_for_change(db, session.workspace_id, document_id, if_match)
        updated_at, version = await repository.update_document(
            db, session.workspace_id, document_id, values
        )
    # DocumentPatch fields are named like Document fields.
    return _to_document(stored, keys).model_copy(
        update={**changes, "updated_at": updated_at, "version": version}
    )


async def delete_document(
    db: AsyncSession, session: SessionContext, document_id: UUID, *, if_match: str
) -> None:
    async with session_tx(db, session):
        await _locked_for_change(db, session.workspace_id, document_id, if_match)
        await repository.soft_delete(db, session.workspace_id, document_id)


async def _locked_for_change(
    db: AsyncSession, workspace_id: UUID, document_id: UUID, if_match: str
) -> repository.StoredDocument:
    stored = await repository.get_document(db, workspace_id, document_id, for_update=True)
    if stored is None:
        raise ProblemError(ErrorCode.NOT_FOUND)
    if not etag_matches(if_match, stored.version):
        raise ProblemError(ErrorCode.VERSION_CONFLICT, etag=etag(stored.version))
    return stored


async def open_content(
    db: AsyncSession,
    session: SessionContext,
    keys: WorkspaceKeys,
    storage: ObjectStorage,
    document_id: UUID,
    *,
    range_header: str | None,
) -> Download:
    async with session_tx(db, session):
        stored = await repository.get_document(db, session.workspace_id, document_id)
    if stored is None:
        raise ProblemError(ErrorCode.NOT_FOUND)
    byte_range = parse_range(range_header, stored.size_bytes)
    chunks = await asyncio.to_thread(
        open_plaintext,
        storage,
        keys,
        object_key=stored.object_key,
        document_id=document_id,
        byte_range=byte_range,
    )
    return Download(
        title=keys.decrypt_field(stored.title_ct, document_id.bytes),
        document_date=stored.document_date,
        size_bytes=stored.size_bytes,
        byte_range=byte_range,
        chunks=chunks,
    )


def _to_document(stored: repository.StoredDocument, keys: WorkspaceKeys) -> Document:
    aad = stored.id.bytes
    return Document(
        id=stored.id,
        title=keys.decrypt_field(stored.title_ct, aad),
        type=stored.type_code,
        document_date=stored.document_date,
        uploaded_at=stored.uploaded_at,
        updated_at=stored.updated_at,
        note=keys.decrypt_field(stored.note_ct, aad) if stored.note_ct else None,
        file=FileInfo(
            original_name=keys.decrypt_field(stored.original_name_ct, aad),
            size_bytes=stored.size_bytes,
            page_count=stored.page_count,
        ),
        version=stored.version,
    )
