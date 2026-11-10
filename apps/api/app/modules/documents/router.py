from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BeforeValidator

from app.core.deps import Db, Scope, SessionContext, require_scope
from app.core.errors import ErrorCode, ProblemError, problem_responses
from app.core.idempotency import Operation, StoredResponse, require_idempotency_key, run_idempotent
from app.core.ratelimit import (
    DOCUMENTS_CONTENT,
    DOCUMENTS_CREATE,
    DOCUMENTS_DELETE,
    DOCUMENTS_GET,
    DOCUMENTS_LIST,
    DOCUMENTS_UPDATE,
    rate_limit,
)
from app.modules.documents import queries, service
from app.modules.documents.dependencies import (
    Keys,
    PageTokens,
    Storage,
    UserTimezone,
    today_in,
)
from app.modules.documents.filenames import content_disposition
from app.modules.documents.listing import (
    DEFAULT_ORDER,
    DateField,
    OrderBy,
    build_filter,
    parse_timezone,
)
from app.modules.documents.schemas import (
    Document,
    DocumentCreate,
    DocumentList,
    DocumentPatch,
    IsoDate,
    TypeCode,
)

router = APIRouter(prefix="/api/v1", tags=["documents"])

ReadSession = Annotated[SessionContext, Depends(require_scope(Scope.DOCUMENTS_READ))]
WriteSession = Annotated[SessionContext, Depends(require_scope(Scope.DOCUMENTS_WRITE))]
# openapi.yaml: `q` pattern and length; 1 or 2 non-space characters are 422 validation_error.
QUERY_PATTERN = r"^\s*$|^\s*(\S\s*){3,}$"
MAX_PAGE_SIZE = 200
PDF_HEADERS = {
    "Content-Security-Policy": "sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
    "Accept-Ranges": "bytes",
}


def _split_csv(value: Any) -> Any:
    """`type=analysis,conclusion` (style form, explode false) as a list of codes."""
    if isinstance(value, list):
        return [code for item in value for code in str(item).split(",") if code]
    return value


TypeList = Annotated[list[TypeCode] | None, BeforeValidator(_split_csv)]


def _require_if_match(if_match: str | None) -> str:
    if not if_match:
        raise ProblemError(ErrorCode.PRECONDITION_REQUIRED)
    return if_match


# Routes whose contract has no 422 read path, query and headers from the request: a declared
# parameter makes FastAPI add 422 to the operation. An id that is not a UUID is simply not found.
def path_document_id(request: Request) -> UUID:
    try:
        return UUID(request.path_params["document_id"])
    except ValueError:
        raise ProblemError(ErrorCode.NOT_FOUND) from None


DocumentId = Annotated[UUID, Depends(path_document_id)]


@router.get(
    "/documents",
    operation_id="documents.list",
    response_model=DocumentList,
    responses=problem_responses(400, 401, 403, 422, 429, 500),
    dependencies=[Depends(rate_limit(DOCUMENTS_LIST))],
)
async def list_documents(
    db: Db,
    session: ReadSession,
    keys: Keys,
    page_tokens: PageTokens,
    user_timezone: UserTimezone,
    q: Annotated[str | None, Query(max_length=100, pattern=QUERY_PATTERN)] = None,
    types: Annotated[TypeList, Query(alias="type")] = None,
    date_field: DateField = "document",
    date_from: Annotated[IsoDate, Query(alias="from")] = None,
    date_to: Annotated[IsoDate, Query(alias="to")] = None,
    undated: bool = False,
    tz: str | None = None,
    order_by: OrderBy = DEFAULT_ORDER,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    page_token: str | None = None,
) -> DocumentList:
    zone = parse_timezone(tz or user_timezone).key
    list_filter = build_filter(
        q=q,
        types=list(types or ()),
        date_field=date_field,
        date_from=date_from,
        date_to=date_to,
        undated=undated,
    )
    return await queries.list_documents(
        db,
        session,
        keys,
        page_tokens,
        list_filter=list_filter,
        tz=zone,
        order_by=order_by,
        page_size=page_size,
        page_token=page_token or None,
    )


@router.post(
    "/documents",
    operation_id="documents.create",
    status_code=status.HTTP_201_CREATED,
    response_model=Document,
    responses=problem_responses(400, 401, 403, 404, 409, 410, 415, 422, 429, 500, 503),
    dependencies=[Depends(rate_limit(DOCUMENTS_CREATE))],
)
async def create_document(
    db: Db,
    session: WriteSession,
    key: Annotated[str, Depends(require_idempotency_key)],
    payload: DocumentCreate,
    keys: Keys,
    storage: Storage,
    user_timezone: UserTimezone,
) -> JSONResponse:
    async def execute() -> StoredResponse:
        document = await service.create_document(
            db, session, keys, storage, payload, today=today_in(user_timezone)
        )
        return StoredResponse(
            status=status.HTTP_201_CREATED,
            body=document.model_dump(mode="json"),
            headers={
                "ETag": service.etag(document.version),
                "Location": f"/api/v1/documents/{document.id}",
            },
            resource_id=document.id,
        )

    stored = await run_idempotent(
        db,
        session,
        keys,
        operation=Operation.DOCUMENTS_CREATE,
        key=key,
        payload=payload,
        execute=execute,
    )
    return stored.to_response()


@router.get(
    "/documents/{document_id}",
    operation_id="documents.get",
    response_model=Document,
    responses={
        status.HTTP_304_NOT_MODIFIED: {"description": "Не изменился"},
        **problem_responses(401, 403, 404, 429, 500),
    },
    dependencies=[Depends(rate_limit(DOCUMENTS_GET))],
)
async def get_document(
    request: Request, document_id: DocumentId, db: Db, session: ReadSession, keys: Keys
) -> Response:
    document = await service.get_document(db, session, keys, document_id)
    headers = {"ETag": service.etag(document.version)}
    if_none_match = request.headers.get("If-None-Match")
    if if_none_match and service.etag_matches(if_none_match, document.version):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return JSONResponse(document.model_dump(mode="json"), headers=headers)


@router.patch(
    "/documents/{document_id}",
    operation_id="documents.update",
    response_model=Document,
    responses=problem_responses(401, 403, 404, 412, 422, 428, 429, 500),
    dependencies=[Depends(rate_limit(DOCUMENTS_UPDATE))],
)
async def update_document(
    request: Request,
    document_id: DocumentId,
    db: Db,
    session: WriteSession,
    payload: DocumentPatch,
    keys: Keys,
    user_timezone: UserTimezone,
) -> JSONResponse:
    document = await service.update_document(
        db,
        session,
        keys,
        document_id,
        payload,
        if_match=_require_if_match(request.headers.get("If-Match")),
        today=today_in(user_timezone),
    )
    return JSONResponse(
        document.model_dump(mode="json"), headers={"ETag": service.etag(document.version)}
    )


@router.delete(
    "/documents/{document_id}",
    operation_id="documents.delete",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=problem_responses(401, 403, 404, 412, 428, 429, 500),
    dependencies=[Depends(rate_limit(DOCUMENTS_DELETE))],
)
async def delete_document(
    request: Request, document_id: DocumentId, db: Db, session: WriteSession
) -> Response:
    if_match = _require_if_match(request.headers.get("If-Match"))
    await service.delete_document(db, session, document_id, if_match=if_match)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/documents/{document_id}/content",
    operation_id="documents.content",
    response_class=StreamingResponse,
    responses={
        status.HTTP_200_OK: {"content": {"application/pdf": {}}, "description": "PDF"},
        status.HTTP_206_PARTIAL_CONTENT: {
            "content": {"application/pdf": {}},
            "description": "Часть файла",
        },
        **problem_responses(401, 403, 404, 429, 500, 503),
    },
    dependencies=[Depends(rate_limit(DOCUMENTS_CONTENT))],
)
async def document_content(
    request: Request,
    document_id: DocumentId,
    db: Db,
    session: ReadSession,
    keys: Keys,
    storage: Storage,
) -> StreamingResponse:
    download = await service.open_content(
        db, session, keys, storage, document_id, range_header=request.headers.get("Range")
    )
    disposition = (
        "attachment" if request.query_params.get("disposition") == "attachment" else "inline"
    )
    headers = {
        **PDF_HEADERS,
        "Content-Disposition": content_disposition(
            disposition, download.title, download.document_date
        ),
        "Content-Length": str(download.size_bytes),
    }
    status_code = status.HTTP_200_OK
    if download.byte_range is not None:
        status_code = status.HTTP_206_PARTIAL_CONTENT
        headers["Content-Range"] = download.byte_range.content_range(download.size_bytes)
        headers["Content-Length"] = str(download.byte_range.length)
    return StreamingResponse(
        download.chunks, status_code=status_code, media_type="application/pdf", headers=headers
    )
