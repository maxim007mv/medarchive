from datetime import datetime
from functools import cache
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.core.deps import Scope
from app.modules.auth.consent import POLICY_VERSION

DEFAULT_TIMEZONE = "Europe/Moscow"


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConsentIn(_Input):
    policy_version: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    accepted: Literal[True]

    @field_validator("policy_version")
    @classmethod
    def _current_policy(cls, value: str) -> str:
        # The evidence hash is computed from this version's texts; another one was not shown.
        if value != POLICY_VERSION:
            raise ValueError("unknown policy version")
        return value


class WorkspaceCreate(_Input):
    consent: ConsentIn
    timezone: Annotated[str, StringConstraints(max_length=64)] = DEFAULT_TIMEZONE

    @field_validator("timezone")
    @classmethod
    def _iana_zone(cls, value: str) -> str:
        if value not in _zones():
            raise ValueError("unknown time zone")
        return value


class AccessKeyLogin(_Input):
    access_key: Annotated[str, StringConstraints(min_length=24, max_length=29)]


class WorkspaceBrief(BaseModel):
    id: UUID
    created_at: datetime
    document_count: int


class WorkspaceCreated(BaseModel):
    workspace: WorkspaceBrief
    access_key: str
    csrf_token: str
    scopes: list[Scope]


class SessionOut(BaseModel):
    workspace_id: UUID
    csrf_token: str
    scopes: list[Scope]
    idle_expires_at: datetime | None = None
    timezone: str | None = None


@cache
def _zones() -> frozenset[str]:
    return frozenset(available_timezones())
