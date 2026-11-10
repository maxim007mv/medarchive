from datetime import UTC, datetime
from ipaddress import ip_network
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.client import client_ip
from app.core.crypto import Kek
from app.core.deps import (
    OWNER_SCOPES,
    Db,
    Scope,
    SessionContext,
    get_kek,
    require_scope,
)
from app.core.errors import problem_responses
from app.core.idempotency import IDEMPOTENT_REPLAYED, require_idempotency_key
from app.core.ratelimit import GENERAL, SESSIONS_CREATE, WORKSPACES_CREATE, rate_limit
from app.core.security import SESSION_COOKIE, csrf_token
from app.modules.auth import service
from app.modules.auth.repository import SESSION_IDLE_TTL, IpPrefix
from app.modules.auth.schemas import AccessKeyLogin, SessionOut, WorkspaceCreate, WorkspaceCreated

router = APIRouter(prefix="/api/v1")

ReadSession = Annotated[SessionContext, Depends(require_scope(Scope.DOCUMENTS_READ))]
_SCOPES = sorted(OWNER_SCOPES)


@router.post(
    "/workspaces",
    operation_id="workspaces.create",
    tags=["workspaces"],
    status_code=status.HTTP_201_CREATED,
    response_model=WorkspaceCreated,
    responses=problem_responses(400, 409, 422, 429, 500),
    dependencies=[Depends(rate_limit(WORKSPACES_CREATE))],
)
async def create_workspace(
    request: Request,
    payload: WorkspaceCreate,
    db: Db,
    kek: Annotated[Kek, Depends(get_kek)],
    key: Annotated[str, Depends(require_idempotency_key)],
) -> JSONResponse:
    created = await service.create_workspace(
        db, kek, key=key, payload=payload, meta=request_meta(request)
    )
    body = {
        **created.body,
        "csrf_token": _csrf(request, created.session),
        "scopes": _SCOPES,
    }
    response = JSONResponse(body, status_code=status.HTTP_201_CREATED)
    if created.replayed:
        response.headers[IDEMPOTENT_REPLAYED] = "true"
    set_session_cookie(response, created.session.cookie, created.session.idle_expires_at)
    return response


@router.get(
    "/session",
    operation_id="session.get",
    tags=["session"],
    response_model=SessionOut,
    responses=problem_responses(401, 403, 429, 500),
    dependencies=[Depends(rate_limit(GENERAL))],
)
async def get_current_session(
    request: Request, response: Response, db: Db, session: ReadSession
) -> SessionOut:
    state = await service.refresh_session(db, session)
    cookie = request.cookies[SESSION_COOKIE]
    set_session_cookie(response, cookie, state.idle_expires_at)
    return SessionOut(
        workspace_id=session.workspace_id,
        csrf_token=csrf_token(_csrf_secret(request), session.session_id),
        scopes=_SCOPES,
        idle_expires_at=state.idle_expires_at,
        timezone=state.timezone,
    )


@router.post(
    "/sessions",
    operation_id="sessions.create",
    tags=["sessions"],
    status_code=status.HTTP_201_CREATED,
    response_model=SessionOut,
    responses=problem_responses(401, 422, 429, 500),
    dependencies=[Depends(rate_limit(SESSIONS_CREATE))],
)
async def open_session(
    request: Request, response: Response, payload: AccessKeyLogin, db: Db
) -> SessionOut:
    issued = await service.open_by_access_key(db, payload.access_key, request_meta(request))
    set_session_cookie(response, issued.cookie, issued.idle_expires_at)
    return SessionOut(
        workspace_id=issued.workspace_id,
        csrf_token=_csrf(request, issued),
        scopes=_SCOPES,
        idle_expires_at=issued.idle_expires_at,
        timezone=issued.timezone,
    )


@router.delete(
    "/sessions/current",
    operation_id="sessions.delete",
    tags=["sessions"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=problem_responses(401, 403, 429, 500),
    dependencies=[Depends(rate_limit(GENERAL))],
)
async def close_session(request: Request, db: Db, session: ReadSession) -> Response:
    await service.end_session(db, session, request_meta(request).ip_prefix)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response


def set_session_cookie(response: Response, cookie: str, idle_expires_at: datetime) -> None:
    """`__Host-` cookie: Secure, Path=/, no Domain; it lives as long as the idle timeout."""
    max_age = int((idle_expires_at - datetime.now(UTC)).total_seconds())
    response.set_cookie(
        SESSION_COOKIE,
        cookie,
        max_age=min(max_age, int(SESSION_IDLE_TTL.total_seconds())),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")


def request_meta(request: Request) -> service.RequestMeta:
    return service.RequestMeta(request.state.request_id, _ip_prefix(request))


def _ip_prefix(request: Request) -> IpPrefix | None:
    """Audit keeps /24 of IPv4 and /48 of IPv6 (07-database, section 9)."""
    address = client_ip(request)
    if address is None:
        return None
    prefix = 24 if address.version == 4 else 48
    return ip_network(address).supernet(new_prefix=prefix)


def _csrf_secret(request: Request) -> str:
    secret: str = request.app.state.settings.csrf_secret.get_secret_value()
    return secret


def _csrf(request: Request, issued: service.IssuedSession) -> str:
    return csrf_token(_csrf_secret(request), issued.session_id)
