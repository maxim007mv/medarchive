"""RFC 9457 problem details with the error catalog of 06-api-contract.md, section 8.

Titles are shown in the UI as is, so they must match the catalog (and docs/texts.md, section 16)
word for word. Problem bodies never carry user field values, file names or stack traces.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

PROBLEM_MEDIA_TYPE = "application/problem+json"
PROBLEM_TYPE_PREFIX = "urn:problem-type:medarchive:"


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    TITLE_REQUIRED = "title_required"
    TITLE_TOO_LONG = "title_too_long"
    DATE_INVALID = "date_invalid"
    DATE_IN_FUTURE = "date_in_future"
    DATE_RANGE_INVALID = "date_range_invalid"
    NOTE_TOO_LONG = "note_too_long"
    TYPE_UNKNOWN = "type_unknown"
    NOT_PDF = "not_pdf"
    FILE_TOO_LARGE = "file_too_large"
    PDF_UNREADABLE = "pdf_unreadable"
    PDF_ENCRYPTED = "pdf_encrypted"
    UPLOAD_NOT_FOUND = "upload_not_found"
    UPLOAD_EXPIRED = "upload_expired"
    UPLOAD_INCOMPLETE = "upload_incomplete"
    NOT_FOUND = "not_found"
    PRECONDITION_REQUIRED = "precondition_required"
    VERSION_CONFLICT = "version_conflict"
    IDEMPOTENCY_KEY_MISSING = "idempotency_key_missing"
    IDEMPOTENCY_KEY_REUSED = "idempotency_key_reused"
    IDEMPOTENCY_IN_PROGRESS = "idempotency_in_progress"
    INVALID_PAGE_TOKEN = "invalid_page_token"  # noqa: S105  # an error code, not a secret
    UNAUTHENTICATED = "unauthenticated"
    ACCESS_KEY_INVALID = "access_key_invalid"
    CSRF_FAILED = "csrf_failed"
    SCOPE_INSUFFICIENT = "scope_insufficient"
    CONSENT_REQUIRED = "consent_required"
    RATE_LIMITED = "rate_limited"
    AI_BUSY = "ai_busy"
    AI_UNAVAILABLE = "ai_unavailable"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    status: int
    title: str


CATALOG: Mapping[ErrorCode, CatalogEntry] = {
    ErrorCode.VALIDATION_ERROR: CatalogEntry(422, "Проверьте выделенные поля"),
    ErrorCode.TITLE_REQUIRED: CatalogEntry(422, "Введите название документа"),
    ErrorCode.TITLE_TOO_LONG: CatalogEntry(422, "Название длиннее 200 символов"),
    ErrorCode.DATE_INVALID: CatalogEntry(422, "Такой даты нет. Проверьте день и месяц"),
    ErrorCode.DATE_IN_FUTURE: CatalogEntry(422, "Дата документа не может быть позже сегодняшней"),
    ErrorCode.DATE_RANGE_INVALID: CatalogEntry(422, "Начало периода позже конца"),
    ErrorCode.NOTE_TOO_LONG: CatalogEntry(422, "Заметка длиннее 2000 символов"),
    ErrorCode.TYPE_UNKNOWN: CatalogEntry(422, "Выберите тип документа"),
    ErrorCode.NOT_PDF: CatalogEntry(
        415, "Файл не добавлен: это не PDF. Сохраните документ в PDF и попробуйте снова"
    ),
    ErrorCode.FILE_TOO_LARGE: CatalogEntry(
        413, "Файл больше 20 МБ. Сожмите PDF или разделите его на части"
    ),
    ErrorCode.PDF_UNREADABLE: CatalogEntry(
        422, "Не удаётся открыть этот PDF. Возможно, он повреждён"
    ),
    ErrorCode.PDF_ENCRYPTED: CatalogEntry(
        422, "PDF требует пароль для открытия. Снимите пароль и загрузите снова"
    ),
    ErrorCode.UPLOAD_NOT_FOUND: CatalogEntry(404, "Загрузка не найдена. Выберите файл ещё раз"),
    ErrorCode.UPLOAD_EXPIRED: CatalogEntry(410, "Загрузка устарела. Выберите файл ещё раз"),
    ErrorCode.UPLOAD_INCOMPLETE: CatalogEntry(409, "Файл ещё не загрузился до конца"),
    ErrorCode.NOT_FOUND: CatalogEntry(404, "Документ не найден. Возможно, он удалён"),
    ErrorCode.PRECONDITION_REQUIRED: CatalogEntry(428, "Обновите страницу и повторите"),
    ErrorCode.VERSION_CONFLICT: CatalogEntry(
        412, "Документ изменился в другой вкладке. Обновите, чтобы увидеть новую версию"
    ),
    ErrorCode.IDEMPOTENCY_KEY_MISSING: CatalogEntry(
        400, "Не получилось сохранить. Попробуйте ещё раз"
    ),
    ErrorCode.IDEMPOTENCY_KEY_REUSED: CatalogEntry(
        422, "Не получилось сохранить. Попробуйте ещё раз"
    ),
    ErrorCode.IDEMPOTENCY_IN_PROGRESS: CatalogEntry(409, "Сохраняем, подождите секунду"),
    ErrorCode.INVALID_PAGE_TOKEN: CatalogEntry(400, "Список обновился. Загружаем заново"),
    ErrorCode.UNAUTHENTICATED: CatalogEntry(
        401, "Сессия закончилась. Откройте архив ключом доступа"
    ),
    ErrorCode.ACCESS_KEY_INVALID: CatalogEntry(401, "Ключ не подошёл. Проверьте символы"),
    ErrorCode.CSRF_FAILED: CatalogEntry(403, "Страница устарела. Обновите её"),
    ErrorCode.SCOPE_INSUFFICIENT: CatalogEntry(403, "Это действие недоступно по этой ссылке"),
    ErrorCode.CONSENT_REQUIRED: CatalogEntry(
        403, "Чтобы хранить медицинские документы, нужно ваше согласие"
    ),
    ErrorCode.RATE_LIMITED: CatalogEntry(429, "Слишком много действий подряд. Повторите через N с"),
    ErrorCode.AI_BUSY: CatalogEntry(
        429, "Подсказка сейчас занята. Заполните поля вручную или повторите через N с"
    ),
    ErrorCode.AI_UNAVAILABLE: CatalogEntry(503, "Подсказка недоступна. Заполните поля вручную"),
    ErrorCode.STORAGE_UNAVAILABLE: CatalogEntry(
        503, "Хранилище временно недоступно. Попробуйте через минуту"
    ),
    ErrorCode.INTERNAL: CatalogEntry(
        500, "Не получилось выполнить действие. Попробуйте ещё раз через минуту"
    ),
}


@dataclass(frozen=True, slots=True)
class FieldError:
    """One entry of `errors[]`: JSON pointer into the request plus a catalog code."""

    pointer: str
    code: ErrorCode = ErrorCode.VALIDATION_ERROR

    def as_dict(self) -> dict[str, str]:
        return {"pointer": self.pointer, "code": self.code, "title": CATALOG[self.code].title}


class ProblemError(Exception):
    """Raise anywhere in a request to answer with a catalog problem.

    `detail` must never contain user data (titles, notes, file names).
    """

    def __init__(
        self,
        code: ErrorCode,
        *,
        detail: str | None = None,
        errors: Sequence[FieldError] = (),
        etag: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.detail = detail
        self.errors = tuple(errors)
        self.etag = etag
        self.headers = dict(headers or {})

    @property
    def status(self) -> int:
        return CATALOG[self.code].status


def problem_body(
    code: ErrorCode,
    request_id: str,
    *,
    detail: str | None = None,
    errors: Sequence[FieldError] = (),
    etag: str | None = None,
) -> dict[str, Any]:
    entry = CATALOG[code]
    body: dict[str, Any] = {
        "type": PROBLEM_TYPE_PREFIX + code,
        "title": entry.title,
        "status": entry.status,
        "code": code,
        "request_id": request_id,
    }
    if detail is not None:
        body["detail"] = detail
    if errors:
        body["errors"] = [error.as_dict() for error in errors]
    if etag is not None:
        body["etag"] = etag
    return body


def problem_response(
    code: ErrorCode,
    request_id: str,
    *,
    detail: str | None = None,
    errors: Sequence[FieldError] = (),
    etag: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        problem_body(code, request_id, detail=detail, errors=errors, etag=etag),
        status_code=CATALOG[code].status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=dict(headers or {}),
    )


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """`responses=` for a route: the error statuses it declares in openapi.yaml."""
    return {
        status: {"description": "Problem", "content": {PROBLEM_MEDIA_TYPE: {}}}
        for status in statuses
    }


def json_pointer(location: Sequence[int | str]) -> str:
    """Pointer to the offending field: `("body", "consent", "accepted")` -> `/consent/accepted`.

    Query, header and path parameters are addressed by name the same way: `/page_size`.
    """
    parts = [str(part) for part in location[1:]] or [str(location[0])]
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


def field_errors(exc: RequestValidationError) -> list[FieldError]:
    """Map pydantic errors to `errors[]` without echoing the rejected values.

    A validator can pick a specific catalog code by raising
    `PydanticCustomError("title_too_long", ...)`; every other error type is `validation_error`.
    """
    codes = {code.value for code in ErrorCode}
    return [
        FieldError(
            pointer=json_pointer(error["loc"]),
            code=ErrorCode(error["type"]) if error["type"] in codes else ErrorCode.VALIDATION_ERROR,
        )
        for error in exc.errors()
    ]


def request_id_of(request: Request) -> str:
    request_id: str = request.state.request_id
    return request_id


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def problem_error(request: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(
            exc.code,
            request_id_of(request),
            detail=exc.detail,
            errors=exc.errors,
            etag=exc.etag,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem_response(
            ErrorCode.VALIDATION_ERROR, request_id_of(request), errors=field_errors(exc)
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Unknown routes and methods: the catalog has no generic codes for them, so 404 reuses
        # `not_found` and the rest keep their HTTP status with the closest catalog code.
        request_id = request_id_of(request)
        if exc.status_code == 404:
            return problem_response(ErrorCode.NOT_FOUND, request_id)
        # FastAPI raises 400 for a body it cannot decode; the contract calls any malformed
        # input 422 validation_error. Our own 400s are ProblemError and never reach here.
        if exc.status_code == 400:
            return problem_response(ErrorCode.VALIDATION_ERROR, request_id)
        headers = dict(exc.headers or {})
        if exc.status_code == 405:
            headers["Allow"] = _allowed_methods(app, request)
        code = ErrorCode.VALIDATION_ERROR if exc.status_code < 500 else ErrorCode.INTERNAL
        body = problem_body(code, request_id)
        body["status"] = exc.status_code
        return JSONResponse(
            body, status_code=exc.status_code, media_type=PROBLEM_MEDIA_TYPE, headers=headers
        )


def _allowed_methods(app: FastAPI, request: Request) -> str:
    # Starlette's 405 lists only the methods of the first route with this path, but GET and
    # DELETE /api/v1/workspace are two routes.
    methods = {
        method
        for route in app.routes
        if isinstance(route, APIRoute) and route.matches(request.scope)[0] is not Match.NONE
        for method in route.methods or ()
    }
    return ", ".join(sorted(methods))
