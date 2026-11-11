"""POST /api/v1/suggestions stays in the contract with the AI suggestion turned off (ADR-042).

The request goes through the same session, CSRF, Idempotency-Key, limit and body checks as any
other write, then gets 503 `ai_unavailable`.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.core.deps import Scope, require_scope
from app.core.errors import ErrorCode, ProblemError, problem_responses
from app.core.idempotency import require_idempotency_key
from app.core.ratelimit import SUGGESTIONS_CREATE, rate_limit

router = APIRouter(prefix="/api/v1", tags=["suggestions"])


class SuggestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID


@router.post(
    "/suggestions",
    operation_id="suggestions.create",
    responses=problem_responses(400, 401, 403, 404, 409, 410, 422, 429, 500, 503),
    dependencies=[
        Depends(rate_limit(SUGGESTIONS_CREATE)),
        Depends(require_scope(Scope.DOCUMENTS_WRITE)),
        Depends(require_idempotency_key),
    ],
)
async def create_suggestion(payload: SuggestionCreate) -> None:
    raise ProblemError(ErrorCode.AI_UNAVAILABLE)
