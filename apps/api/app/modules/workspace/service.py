"""Archive summary, key rotation and deletion (BE-04, BE-05, BE-10)."""

import asyncio
import hashlib
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import Kek
from app.core.deps import SessionContext, load_workspace_keys, session_tx
from app.core.errors import ErrorCode, ProblemError
from app.core.idempotency import Operation, StoredResponse, run_idempotent
from app.modules.auth import repository as auth_repository
from app.modules.auth.access_key import generate_access_key, hash_secret
from app.modules.auth.repository import IpPrefix
from app.modules.workspace import repository
from app.modules.workspace.schemas import AccessKeyIssued, DocumentTypeList, WorkspaceOut

ANY_ETAG = "*"


def workspace_etag(summary: WorkspaceOut) -> str:
    """Strong ETag of what the person saw: any document, size or consent change alters it."""
    digest = hashlib.sha256(summary.model_dump_json().encode()).hexdigest()
    return f'"w{digest[:16]}"'


async def get_summary(db: AsyncSession, session: SessionContext) -> WorkspaceOut:
    async with session_tx(db, session):
        summary = await repository.workspace_summary(db, session.workspace_id)
    if summary is None:
        raise ProblemError(ErrorCode.UNAUTHENTICATED)
    return summary


async def delete_workspace(
    db: AsyncSession, session: SessionContext, if_match: str | None, ip_prefix: IpPrefix | None
) -> datetime:
    """Crypto-erase the archive if `If-Match` still matches; returns the purge deadline."""
    if not if_match:
        raise ProblemError(ErrorCode.PRECONDITION_REQUIRED)
    async with session_tx(db, session):
        summary = await repository.workspace_summary(db, session.workspace_id)
        if summary is None:
            raise ProblemError(ErrorCode.UNAUTHENTICATED)
        current = workspace_etag(summary)
        if if_match.strip() not in (current, ANY_ETAG):
            raise ProblemError(ErrorCode.VERSION_CONFLICT, etag=current)
        purge_after = await repository.delete_workspace(db)
        if purge_after is None:
            raise ProblemError(ErrorCode.UNAUTHENTICATED)
        for action in ("workspace.delete", "consent.withdraw"):
            await auth_repository.add_audit(
                db,
                session.workspace_id,
                action,
                session_id=session.session_id,
                request_id=session.request_id,
                ip_prefix=ip_prefix,
            )
    return purge_after


async def rotate_access_key(
    db: AsyncSession, kek: Kek, session: SessionContext, key: str, ip_prefix: IpPrefix | None
) -> StoredResponse:
    """New access key, previous one revoked; a repeated Idempotency-Key returns the same key."""
    async with session_tx(db, session):
        keys = await load_workspace_keys(db, kek, session.workspace_id)

    async def issue() -> StoredResponse:
        access_key = generate_access_key()
        secret_hash = await asyncio.to_thread(hash_secret, access_key.secret)
        async with session_tx(db, session):
            revoked_previous = await auth_repository.issue_access_key(
                db, access_key.lookup_id, secret_hash
            )
            await auth_repository.add_audit(
                db,
                session.workspace_id,
                "access_key.issue",
                session_id=session.session_id,
                request_id=session.request_id,
                ip_prefix=ip_prefix,
            )
        body = AccessKeyIssued(access_key=access_key.display, revoked_previous=revoked_previous)
        return StoredResponse(status=201, body=body.model_dump(mode="json"))

    return await run_idempotent(
        db,
        session,
        keys,
        operation=Operation.WORKSPACE_ROTATE_KEY,
        key=key,
        payload=None,
        execute=issue,
    )


async def list_document_types(db: AsyncSession) -> DocumentTypeList:
    async with db.begin():
        return DocumentTypeList(items=await repository.document_types(db))
