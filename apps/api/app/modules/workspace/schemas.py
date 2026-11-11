from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ConsentOut(BaseModel):
    policy_version: str
    accepted_at: datetime


class WorkspaceOut(BaseModel):
    id: UUID
    created_at: datetime
    document_count: int
    total_bytes: int
    undated_count: int
    consent: ConsentOut | None = None


class AccessKeyIssued(BaseModel):
    access_key: str
    revoked_previous: bool


class DeletionScheduled(BaseModel):
    status: Literal["scheduled"] = "scheduled"
    purge_before: datetime


class DocumentTypeOut(BaseModel):
    code: Literal["analysis", "conclusion", "other"]
    title: str


class DocumentTypeList(BaseModel):
    items: list[DocumentTypeOut]
