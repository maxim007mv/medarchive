"""Request and response bodies of the documents operations (openapi.yaml, components.schemas).

Validators raise catalog codes (`title_required`, `date_invalid`, ...) as pydantic error types,
so `errors[].code` in the 422 answer names the exact rule.
"""

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

MAX_TITLE_CHARS = 200
MAX_NOTE_CHARS = 2000
# documents CHECK (document_date >= DATE '1900-01-01').
MIN_DOCUMENT_DATE = date(1900, 1, 1)
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

TypeCode = Literal["analysis", "conclusion", "other"]


def _catalog_error(code: str) -> PydanticCustomError:
    return PydanticCustomError(code, code)


def _title(value: str) -> str:
    title = value.strip()
    if not title:
        raise _catalog_error("title_required")
    if len(title) > MAX_TITLE_CHARS:
        raise _catalog_error("title_too_long")
    return title


def _note(value: str | None) -> str | None:
    note = (value or "").strip()
    if len(note) > MAX_NOTE_CHARS:
        raise _catalog_error("note_too_long")
    return note or None


def iso_date_only(value: Any) -> Any:
    """`YYYY-MM-DD` text or a date: pydantic alone would also take 0 or "0" as a Unix time."""
    if value is None or isinstance(value, date):
        return value
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        raise ValueError("expected YYYY-MM-DD")
    return value


def _document_date(value: Any, handler: ValidatorFunctionWrapHandler) -> date | None:
    try:
        parsed: date | None = handler(iso_date_only(value))
    # pydantic's ValidationError is a ValueError too.
    except ValueError:
        raise _catalog_error("date_invalid") from None
    if parsed is not None and parsed < MIN_DOCUMENT_DATE:
        raise _catalog_error("date_invalid")
    return parsed


def _type_code(value: Any, handler: ValidatorFunctionWrapHandler) -> TypeCode:
    try:
        code: TypeCode = handler(value)
    except ValidationError:
        raise _catalog_error("type_unknown") from None
    return code


Title = Annotated[
    str,
    AfterValidator(_title),
    Field(json_schema_extra={"minLength": 1, "maxLength": MAX_TITLE_CHARS}),
]
Note = Annotated[
    str | None, AfterValidator(_note), Field(json_schema_extra={"maxLength": MAX_NOTE_CHARS})
]
DocumentDate = Annotated[date | None, WrapValidator(_document_date)]
# Query and filter dates: a wrong format is plain validation_error.
IsoDate = Annotated[date | None, BeforeValidator(iso_date_only)]
DocumentType = Annotated[TypeCode, WrapValidator(_type_code)]


class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID
    title: Title
    type: DocumentType
    document_date: DocumentDate = None
    note: Note = None


class DocumentPatch(BaseModel):
    """Only the fields present in the body change; `null` clears `note` or `document_date`."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"minProperties": 1})

    title: Title | None = None
    type: DocumentType | None = None
    document_date: DocumentDate = None
    note: Note = None

    @field_validator("title", "type", mode="before")
    @classmethod
    def _not_null(cls, value: Any) -> Any:
        if value is None:
            raise _catalog_error("validation_error")
        return value

    @model_validator(mode="after")
    def _not_empty(self) -> "DocumentPatch":
        if not self.model_fields_set:
            raise _catalog_error("validation_error")
        return self

    def changes(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.model_fields_set}


class FileInfo(BaseModel):
    original_name: str
    size_bytes: int
    page_count: int | None


class Document(BaseModel):
    id: UUID
    title: str
    type: TypeCode
    document_date: date | None
    uploaded_at: datetime
    updated_at: datetime
    note: str | None
    file: FileInfo
    version: int


class DocumentListItem(BaseModel):
    id: UUID
    title: str
    type: TypeCode
    document_date: date | None
    uploaded_at: datetime
    has_note: bool
    size_bytes: int
    version: int


class DocumentList(BaseModel):
    items: list[DocumentListItem]
    total: int
    matched: int
    undated_excluded: int
    next_page_token: str
