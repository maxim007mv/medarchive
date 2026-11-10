from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MAX_UPLOAD_BYTES = 20_971_520
PDF_CONTENT_TYPE = "application/pdf"


class UploadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_name: str = Field(min_length=1, max_length=255)
    # The maximum is checked by the service: above it the answer is 413 `file_too_large`.
    size_bytes: Annotated[int, Field(ge=1, json_schema_extra={"maximum": MAX_UPLOAD_BYTES})]
    # Declared as const in the contract, but another value is 415 `not_pdf`, not 422.
    content_type: Annotated[str, Field(json_schema_extra={"const": PDF_CONTENT_TYPE})]


class Upload(BaseModel):
    upload_id: UUID
    url: str
    fields: dict[str, str]
    max_bytes: int
    expires_at: datetime
