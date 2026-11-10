"""POST /uploads: an uploads row and a presigned POST into the quarantine bucket (BE-06)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import WorkspaceKeys
from app.core.deps import SessionContext, session_tx
from app.core.errors import ErrorCode, ProblemError
from app.core.ids import new_id
from app.modules.uploads import repository
from app.modules.uploads.schemas import (
    MAX_UPLOAD_BYTES,
    PDF_CONTENT_TYPE,
    Upload,
    UploadCreate,
)
from app.storage.s3 import ObjectStorage

SIGNATURE_TTL = timedelta(minutes=15)


def original_name_aad(upload_id: UUID) -> bytes:
    return upload_id.bytes


async def create_upload(
    db: AsyncSession,
    session: SessionContext,
    keys: WorkspaceKeys,
    storage: ObjectStorage,
    body: UploadCreate,
) -> Upload:
    """A declared size over 20 MB is 413 `file_too_large` before anything is stored."""
    if body.size_bytes > MAX_UPLOAD_BYTES:
        raise ProblemError(ErrorCode.FILE_TOO_LARGE)
    if body.content_type != PDF_CONTENT_TYPE:
        raise ProblemError(ErrorCode.NOT_PDF)
    upload_id = new_id()
    async with session_tx(db, session):
        await repository.insert_upload(
            db,
            session.workspace_id,
            upload_id=upload_id,
            max_bytes=MAX_UPLOAD_BYTES,
            original_name_ct=keys.encrypt_field(body.original_name, original_name_aad(upload_id)),
        )
    expires_at = datetime.now(UTC) + SIGNATURE_TTL
    post = storage.presign_quarantine_upload(
        repository.quarantine_key(session.workspace_id, upload_id),
        max_bytes=MAX_UPLOAD_BYTES,
        expires_in_seconds=int(SIGNATURE_TTL.total_seconds()),
    )
    return Upload(
        upload_id=upload_id,
        url=post.url,
        fields=post.fields,
        max_bytes=MAX_UPLOAD_BYTES,
        expires_at=expires_at.replace(microsecond=0),
    )
