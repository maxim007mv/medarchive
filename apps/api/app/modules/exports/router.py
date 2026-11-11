from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.deps import Db, Scope, SessionContext, require_scope
from app.core.errors import ErrorCode, ProblemError, problem_responses
from app.core.idempotency import Operation, StoredResponse, require_idempotency_key, run_idempotent
from app.core.ratelimit import EXPORTS_CONTENT, EXPORTS_CREATE, rate_limit
from app.modules.documents.dependencies import Keys, Storage, UserTimezone, today_in
from app.modules.exports import service
from app.modules.exports.schemas import Export, ExportCreate

router = APIRouter(prefix="/api/v1", tags=["exports"])

ExportSession = Annotated[SessionContext, Depends(require_scope(Scope.EXPORTS_CREATE))]


def path_export_id(request: Request) -> UUID:
    """Read from the request: a declared path parameter would add 422, absent in the contract."""
    try:
        return UUID(request.path_params["export_id"])
    except ValueError:
        raise ProblemError(ErrorCode.NOT_FOUND) from None


@router.post(
    "/exports",
    operation_id="exports.create",
    status_code=status.HTTP_201_CREATED,
    response_model=Export,
    responses=problem_responses(400, 401, 403, 409, 422, 429, 500),
    dependencies=[Depends(rate_limit(EXPORTS_CREATE))],
)
async def create_export(
    db: Db,
    session: ExportSession,
    key: Annotated[str, Depends(require_idempotency_key)],
    payload: ExportCreate,
    keys: Keys,
    user_timezone: UserTimezone,
) -> JSONResponse:
    async def execute() -> StoredResponse:
        export = await service.create_export(db, session, keys, payload, tz=user_timezone)
        return StoredResponse(
            status=status.HTTP_201_CREATED,
            body=export.model_dump(mode="json"),
            resource_id=export.id,
        )

    stored = await run_idempotent(
        db,
        session,
        keys,
        operation=Operation.EXPORTS_CREATE,
        key=key,
        payload=payload,
        execute=execute,
    )
    return stored.to_response()


@router.get(
    "/exports/{export_id}/content",
    operation_id="exports.content",
    response_class=StreamingResponse,
    responses={
        status.HTTP_200_OK: {
            "content": {"application/zip": {}},
            "description": "ZIP: PDF, documents.csv, documents.json",
        },
        **problem_responses(401, 403, 404, 429, 500),
    },
    dependencies=[Depends(rate_limit(EXPORTS_CONTENT))],
)
async def export_content(
    export_id: Annotated[UUID, Depends(path_export_id)],
    db: Db,
    session: ExportSession,
    keys: Keys,
    storage: Storage,
    user_timezone: UserTimezone,
) -> StreamingResponse:
    archive = await service.open_archive(
        db, session, keys, storage, export_id, today=today_in(user_timezone)
    )
    return StreamingResponse(
        archive.chunks,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{archive.file_name}"',
            "Content-Length": str(archive.size_bytes),
            "Cache-Control": "no-store",
        },
    )
