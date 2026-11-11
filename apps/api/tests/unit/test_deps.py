from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import Response
from freezegun import freeze_time

from app.core.deps import OWNER_SCOPES, Scope, SessionContext, require_scope
from app.core.errors import ErrorCode, ProblemError
from app.modules.auth.router import set_session_cookie

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))


def _session(scopes: frozenset[Scope]) -> SessionContext:
    return SessionContext(session_id=uuid4(), workspace_id=uuid4(), scopes=scopes, request_id="r")


async def test_require_scope_passes_session_with_scope() -> None:
    session = _session(OWNER_SCOPES)

    assert await require_scope(Scope.WORKSPACE_MANAGE)(session) is session


async def test_require_scope_rejects_narrower_session() -> None:
    read_only = _session(frozenset({Scope.DOCUMENTS_READ}))

    with pytest.raises(ProblemError) as caught:
        await require_scope(Scope.DOCUMENTS_WRITE)(read_only)

    assert caught.value.code is ErrorCode.SCOPE_INSUFFICIENT


@freeze_time(NOW)
def test_cookie_lives_for_the_idle_timeout() -> None:
    response = Response()

    set_session_cookie(response, "token", NOW + timedelta(days=30))

    assert response.headers["set-cookie"] == (
        "__Host-ma_sid=token; HttpOnly; Max-Age=2592000; Path=/; SameSite=lax; Secure"
    )


@freeze_time(NOW)
def test_cookie_ends_with_the_absolute_timeout() -> None:
    response = Response()

    set_session_cookie(response, "token", NOW + timedelta(hours=2))

    assert "Max-Age=7200;" in response.headers["set-cookie"]
