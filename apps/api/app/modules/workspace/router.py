import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.crypto import Kek
from app.core.deps import Db, Scope, SessionContext, get_kek, require_scope
from app.core.errors import problem_responses
from app.core.idempotency import require_idempotency_key
from app.core.ratelimit import (
    ACCESS_KEY_ROTATE,
    GENERAL,
    WORKSPACE_DELETE,
    RateBudget,
    deferred_rate_limit,
    rate_limit,
)
from app.modules.auth.router import clear_session_cookie, request_meta
from app.modules.workspace import service
from app.modules.workspace.schemas import (
    AccessKeyIssued,
    DeletionScheduled,
    DocumentTypeList,
    WorkspaceOut,
)

router = APIRouter(prefix="/api/v1")

ReadSession = Annotated[SessionContext, Depends(require_scope(Scope.DOCUMENTS_READ))]
ManageSession = Annotated[SessionContext, Depends(require_scope(Scope.WORKSPACE_MANAGE))]
# The reference list holds no personal data (06-api-contract, section 3).
DOCUMENT_TYPES_CACHE = "public, max-age=3600"


@router.get(
    "/workspace",
    operation_id="workspace.get",
    tags=["workspace"],
    response_model=WorkspaceOut,
    response_model_exclude_none=True,
    responses=problem_responses(401, 403, 429, 500),
    dependencies=[Depends(rate_limit(GENERAL))],
)
async def get_workspace(response: Response, db: Db, session: ReadSession) -> WorkspaceOut:
    summary = await service.get_summary(db, session)
    response.headers["ETag"] = service.workspace_etag(summary)
    return summary


@router.delete(
    "/workspace",
    operation_id="workspace.delete",
    tags=["workspace"],
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DeletionScheduled,
    responses=problem_responses(401, 403, 412, 428, 429, 500),
)
async def delete_workspace(
    request: Request,
    response: Response,
    # Before the session: its headers must reach 401 and 403 answers too.
    budget: Annotated[RateBudget, Depends(deferred_rate_limit(WORKSPACE_DELETE))],
    db: Db,
    session: ManageSession,
) -> DeletionScheduled:
    # Read from the raw headers: a declared required header would add a 422 the contract
    # does not have; a missing If-Match is 428.
    purge_before = await service.delete_workspace(
        db, session, request.headers.get("If-Match"), request_meta(request).ip_prefix, budget
    )
    clear_session_cookie(response)
    return DeletionScheduled(purge_before=purge_before)


@router.post(
    "/workspace/access-key",
    operation_id="workspace.rotateKey",
    tags=["workspace"],
    status_code=status.HTTP_201_CREATED,
    response_model=AccessKeyIssued,
    responses=problem_responses(400, 401, 403, 409, 422, 429, 500),
    dependencies=[Depends(rate_limit(ACCESS_KEY_ROTATE))],
)
async def rotate_access_key(
    request: Request,
    db: Db,
    kek: Annotated[Kek, Depends(get_kek)],
    session: ManageSession,
    key: Annotated[str, Depends(require_idempotency_key)],
) -> JSONResponse:
    stored = await service.rotate_access_key(db, kek, session, key, request_meta(request).ip_prefix)
    return stored.to_response()


@router.get(
    "/document-types",
    operation_id="documentTypes.list",
    tags=["documentTypes"],
    response_model=DocumentTypeList,
    responses=problem_responses(401, 403, 429, 500),
    dependencies=[Depends(rate_limit(GENERAL))],
)
async def list_document_types(db: Db, _session: ReadSession) -> JSONResponse:
    types = await service.list_document_types(db)
    body = types.model_dump_json().encode()
    return JSONResponse(
        types.model_dump(mode="json"),
        headers={
            "ETag": f'"t{hashlib.sha256(body).hexdigest()[:16]}"',
            "Cache-Control": DOCUMENT_TYPES_CACHE,
        },
    )
