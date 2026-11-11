from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.listing import DateField
from app.modules.documents.schemas import IsoDate, TypeCode

# exports CHECK (cardinality(document_ids) BETWEEN 1 AND 5000).
MAX_EXPORT_DOCUMENTS = 5000
QUERY_PATTERN = r"^\s*$|^\s*(\S\s*){3,}$"

ExportScope = Literal["all", "filtered", "selected"]


class DocumentFilter(BaseModel):
    """The list filter as a body (openapi.yaml, DocumentFilter)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    q: Annotated[str | None, Field(max_length=100, pattern=QUERY_PATTERN)] = None
    type: list[TypeCode] | None = None
    date_field: DateField | None = None
    date_from: Annotated[IsoDate, Field(alias="from")] = None
    date_to: Annotated[IsoDate, Field(alias="to")] = None
    undated: bool | None = None


class ExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: ExportScope
    filter: DocumentFilter | None = None
    document_ids: Annotated[
        list[UUID] | None, Field(min_length=1, max_length=MAX_EXPORT_DOCUMENTS)
    ] = None


class Export(BaseModel):
    id: UUID
    scope: ExportScope
    document_count: int
    total_bytes: int
    content_url: str
    expires_at: datetime
