"""Outermost request wrapper: request id, security headers, rate limit headers, access log,
RED metrics and the last-resort 500.

Pure ASGI rather than BaseHTTPMiddleware so streamed PDF and ZIP bodies pass through untouched.
It catches unhandled errors itself: Starlette's own 500 is produced outside user middleware and
would lose `X-Request-Id`.
"""

import re
import secrets
import time
import traceback

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import ErrorCode, problem_response
from app.core.metrics import HTTP_DURATION, HTTP_REQUESTS

REQUEST_ID_HEADER = "X-Request-Id"
RATE_LIMIT_HEADERS_STATE = "rate_limit_headers"
_INCOMING_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# Routes may override CSP (PDF answers with `sandbox`) and Cache-Control (public reference data).
_DEFAULT_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cache-Control": "no-store",
}
_HSTS = "max-age=31536000; includeSubDomains"

log = structlog.get_logger("app.request")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        is_https = scope.get("scheme") == "https"
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_headers(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                for name, value in _DEFAULT_HEADERS.items():
                    headers.setdefault(name, value)
                if is_https:
                    headers.setdefault("Strict-Transport-Security", _HSTS)
                for name, value in state.get(RATE_LIMIT_HEADERS_STATE, {}).items():
                    headers.setdefault(name, value)
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception as exc:
            # Type and frames only: exception messages may quote SQL parameters or field values.
            log.error(
                "unhandled_error",
                error_type=type(exc).__name__,
                frames=traceback.format_tb(exc.__traceback__),
            )
            if response_started:
                raise
            response = problem_response(ErrorCode.INTERNAL, request_id)
            await response(scope, receive, send_with_headers)
        finally:
            route = _route_template(scope)
            duration = time.perf_counter() - started
            HTTP_REQUESTS.labels(scope["method"], route, str(status)).inc()
            HTTP_DURATION.labels(scope["method"], route).observe(duration)
            log.info(
                "request",
                method=scope["method"],
                route=route,
                status=status,
                duration_ms=round(duration * 1000, 1),
            )
            structlog.contextvars.unbind_contextvars("request_id")


def _request_id(scope: Scope) -> str:
    incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
    if incoming and _INCOMING_REQUEST_ID.fullmatch(incoming):
        return incoming
    return "req_" + secrets.token_hex(8)


def _route_template(scope: Scope) -> str:
    route = scope.get("route")
    path: str = getattr(route, "path", "unmatched")
    return path
