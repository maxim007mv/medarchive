"""GCRA rate limits in Redis (BE-12; 06-api-contract, sections 3 and 7).

Each policy allows `quota` requests at once and refills one every `window / quota` seconds.
Every response of a limited route carries `RateLimit-Policy` and `RateLimit`, errors included;
over the limit the route answers 429 `rate_limited` with `Retry-After`.
"""

import hashlib
import ipaddress
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum

from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import WatchError

from app.core.errors import ErrorCode, ProblemError
from app.core.middleware import RATE_LIMIT_HEADERS_STATE
from app.core.security import SESSION_COOKIE

_MAX_WATCH_RETRIES = 5


class Subject(Enum):
    """Whose budget a request spends."""

    IP = "ip"
    SESSION = "session"


@dataclass(frozen=True, slots=True)
class RatePolicy:
    name: str
    quota: int
    window_s: int
    subject: Subject

    @property
    def window_ms(self) -> int:
        return self.window_s * 1000

    @property
    def emission_ms(self) -> int:
        """Refill interval; every policy of section 3 divides into whole milliseconds."""
        return self.window_ms // self.quota

    @property
    def header(self) -> str:
        return f'"{self.name}";q={self.quota};w={self.window_s}'


GENERAL = RatePolicy("general", 300, 60, Subject.SESSION)
WORKSPACES_CREATE = RatePolicy("workspaces", 10, 3600, Subject.IP)
SESSIONS_CREATE = RatePolicy("login", 5, 900, Subject.IP)
ACCESS_KEY_ROTATE = RatePolicy("access_key", 5, 3600, Subject.SESSION)
WORKSPACE_DELETE = RatePolicy("workspace_delete", 1, 3600, Subject.SESSION)
UPLOADS_CREATE = RatePolicy("uploads", 30, 60, Subject.SESSION)
SUGGESTIONS_CREATE = RatePolicy("suggestions", 10, 60, Subject.SESSION)
DOCUMENTS_CREATE = RatePolicy("documents_create", 30, 60, Subject.SESSION)
DOCUMENTS_LIST = RatePolicy("documents_list", 120, 60, Subject.SESSION)
DOCUMENTS_GET = RatePolicy("documents_get", 120, 60, Subject.SESSION)
DOCUMENTS_CONTENT = RatePolicy("documents_content", 120, 60, Subject.SESSION)
DOCUMENTS_UPDATE = RatePolicy("documents_update", 60, 60, Subject.SESSION)
DOCUMENTS_DELETE = RatePolicy("documents_delete", 60, 60, Subject.SESSION)
EXPORTS_CREATE = RatePolicy("exports_create", 6, 60, Subject.SESSION)
EXPORTS_CONTENT = RatePolicy("exports_content", 6, 60, Subject.SESSION)


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    remaining: int
    # Seconds until the full quota is back (allowed) or until the next request fits (denied).
    reset_s: int
    # Theoretical arrival time (Unix ms) to store; None when denied (state unchanged).
    new_tat_ms: int | None


def gcra(policy: RatePolicy, stored_tat_ms: int | None, now_ms: int) -> Decision:
    """Pure GCRA step: `stored_tat_ms` is the theoretical arrival time saved by the last hit."""
    new_tat_ms = max(stored_tat_ms or now_ms, now_ms) + policy.emission_ms
    allow_at_ms = new_tat_ms - policy.window_ms
    if now_ms < allow_at_ms:
        return Decision(False, 0, _seconds(allow_at_ms - now_ms), None)
    remaining = (policy.window_ms - (new_tat_ms - now_ms)) // policy.emission_ms
    return Decision(True, remaining, _seconds(new_tat_ms - now_ms), new_tat_ms)


def _seconds(duration_ms: int) -> int:
    return max(1, math.ceil(duration_ms / 1000))


class RateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def hit(self, policy: RatePolicy, subject: str) -> Decision:
        """Spend one request; fails closed (denied) if the key stays contended."""
        key = f"rl:{policy.name}:{subject}"
        async with self._redis.pipeline(transaction=True) as pipe:
            for _ in range(_MAX_WATCH_RETRIES):
                try:
                    await pipe.watch(key)
                    raw = await pipe.get(key)
                    now_ms = time.time_ns() // 1_000_000
                    decision = gcra(policy, int(raw) if raw else None, now_ms)
                    if decision.new_tat_ms is None:
                        return decision  # leaving the pipeline context resets the WATCH
                    pipe.multi()  # type: ignore[no-untyped-call]  # unannotated in redis-py 8
                    pipe.set(key, decision.new_tat_ms, px=decision.new_tat_ms - now_ms)
                    await pipe.execute()
                    return decision
                except WatchError:
                    continue
        return Decision(False, 0, 1, None)


def rate_limit(policy: RatePolicy) -> Callable[[Request], Awaitable[None]]:
    """Route dependency: `dependencies=[Depends(rate_limit(UPLOADS_CREATE))]`.

    Put it in the route's `dependencies` so it runs before authentication and its headers
    reach 401 and 403 answers too.
    """

    async def dependency(request: Request) -> None:
        subject = _subject(request, policy)
        if subject is None:
            # No session to spend: authentication answers 401 before any database work.
            decision = Decision(True, policy.quota, 0, None)
        else:
            limiter: RateLimiter = request.app.state.rate_limiter
            decision = await limiter.hit(policy, subject)
        setattr(
            request.state,
            RATE_LIMIT_HEADERS_STATE,
            {
                "RateLimit-Policy": policy.header,
                "RateLimit": f'"{policy.name}";r={decision.remaining};t={decision.reset_s}',
            },
        )
        if not decision.allowed:
            raise ProblemError(
                ErrorCode.RATE_LIMITED, headers={"Retry-After": str(decision.reset_s)}
            )

    return dependency


def _subject(request: Request, policy: RatePolicy) -> str | None:
    """Budget key; None for a session policy without a session cookie."""
    if policy.subject is Subject.IP:
        return "ip:" + client_network(request)
    # Keyed by a hash of the cookie, not the resolved session: the limit runs before
    # authentication, so a forged cookie spends its own budget and then gets 401.
    cookie = request.cookies.get(SESSION_COOKIE)
    return "s:" + hashlib.sha256(cookie.encode()).hexdigest()[:32] if cookie else None


def client_network(request: Request) -> str:
    """Client address; IPv6 clients are grouped by /64 (06-api-contract, section 7)."""
    host = request.client.host if request.client else "unknown"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)
