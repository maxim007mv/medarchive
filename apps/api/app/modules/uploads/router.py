from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.deps import Db, Scope, SessionContext, require_scope
from app.core.errors import problem_responses
from app.core.idempotency import Operation, StoredResponse, require_idempotency_key, run_idempotent
from app.core.ratelimit import UPLOADS_CREATE, rate_limit
from app.modules.documents.dependencies import Keys, Storage
from app.modules.uploads import service
from app.modules.uploads.schemas import Upload, UploadCreate

router = APIRouter(prefix="/api/v1", tags=["uploads"])


@router.post(
    "/uploads",
    operation_id="uploads.create",
    status_code=status.HTTP_201_CREATED,
    response_model=Upload,
    responses=problem_responses(400, 401, 403, 409, 413, 415, 422, 429, 500),
    dependencies=[Depends(rate_limit(UPLOADS_CREATE))],
)
async def create_upload(
    db: Db,
    session: Annotated[SessionContext, Depends(require_scope(Scope.DOCUMENTS_WRITE))],
    key: Annotated[str, Depends(require_idempotency_key)],
    payload: UploadCreate,
    keys: Keys,
    storage: Storage,
) -> JSONResponse:
    async def execute() -> StoredResponse:
        upload = await service.create_upload(db, session, keys, storage, payload)
        return StoredResponse(
            status=status.HTTP_201_CREATED,
            body=upload.model_dump(mode="json"),
            resource_id=upload.upload_id,
        )

    stored = await run_idempotent(
        db,
        session,
        keys,
        operation=Operation.UPLOADS_CREATE,
        key=key,
        payload=payload,
        execute=execute,
    )
    return stored.to_response()
