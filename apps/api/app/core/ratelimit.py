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

from app.core.client import client_ip
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


def gcra_peek(policy: RatePolicy, stored_tat_ms: int | None, now_ms: int) -> Decision:
    """The budget as it stands, without spending: `remaining` requests fit right now."""
    tat_ms = max(stored_tat_ms or now_ms, now_ms)
    remaining = (policy.window_ms - (tat_ms - now_ms)) // policy.emission_ms
    if remaining < 1:
        next_fits_in_ms = tat_ms + policy.emission_ms - policy.window_ms - now_ms
        return Decision(False, 0, _seconds(next_fits_in_ms), None)
    reset_s = _seconds(tat_ms - now_ms) if tat_ms > now_ms else 0
    return Decision(True, remaining, reset_s, None)


def gcra_refund(policy: RatePolicy, stored_tat_ms: int) -> int:
    """TAT after giving one spent request back; a TAT in the past means a full budget."""
    return stored_tat_ms - policy.emission_ms


def _seconds(duration_ms: int) -> int:
    return max(1, math.ceil(duration_ms / 1000))


class RateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def hit(self, policy: RatePolicy, subject: str) -> Decision:
        """Spend one request; fails closed (denied) if the key stays contended."""

        def step(stored_tat_ms: int | None, now_ms: int) -> tuple[Decision, int | None]:
            decision = gcra(policy, stored_tat_ms, now_ms)
            return decision, decision.new_tat_ms

        decision = await self._transact(_key(policy, subject), step)
        return decision or Decision(False, 0, 1, None)

    async def peek(self, policy: RatePolicy, subject: str) -> Decision:
        raw = await self._redis.get(_key(policy, subject))
        return gcra_peek(policy, int(raw) if raw else None, _now_ms())

    async def refund(self, policy: RatePolicy, subject: str) -> None:
        """Give back a request spent by `hit` for an operation that did not happen."""

        def step(stored_tat_ms: int | None, _now_ms: int) -> tuple[None, int | None]:
            if stored_tat_ms is None:
                return None, None
            return None, gcra_refund(policy, stored_tat_ms)

        await self._transact(_key(policy, subject), step)

    async def _transact[T](
        self, key: str, step: Callable[[int | None, int], tuple[T, int | None]]
    ) -> T | None:
        """Read the TAT, compute, write back atomically (WATCH/MULTI); None if contended.

        `step` returns the result and the TAT to store: None keeps the key as is, a TAT that is
        not in the future deletes it.
        """
        async with self._redis.pipeline(transaction=True) as pipe:
            for _ in range(_MAX_WATCH_RETRIES):
                try:
                    await pipe.watch(key)
                    raw = await pipe.get(key)
                    now_ms = _now_ms()
                    result, new_tat_ms = step(int(raw) if raw else None, now_ms)
                    if new_tat_ms is None:
                        return result  # leaving the pipeline context resets the WATCH
                    pipe.multi()  # type: ignore[no-untyped-call]  # unannotated in redis-py 8
                    if new_tat_ms > now_ms:
                        pipe.set(key, new_tat_ms, px=new_tat_ms - now_ms)
                    else:
                        pipe.delete(key)
                    await pipe.execute()
                    return result
                except WatchError:
                    continue
        return None


class RateBudget:
    """A budget spent only when the operation is accepted (see `deferred_rate_limit`)."""

    def __init__(
        self, request: Request, policy: RatePolicy, subject: str | None, limiter: RateLimiter
    ) -> None:
        self._request = request
        self._policy = policy
        self._subject = subject
        self._limiter = limiter
        self._spent = False

    async def consume(self) -> None:
        """Spend one request at the accept point; 429 `rate_limited` if none is left."""
        if self._subject is None:
            return
        decision = await self._limiter.hit(self._policy, self._subject)
        _publish(self._request, self._policy, decision)
        if not decision.allowed:
            raise _rate_limited(decision)
        self._spent = True

    async def refund(self) -> None:
        """Undo `consume` when the accepted operation failed before it took effect."""
        if self._spent and self._subject is not None:
            await self._limiter.refund(self._policy, self._subject)
            self._spent = False


def deferred_rate_limit(policy: RatePolicy) -> Callable[[Request], Awaitable[RateBudget]]:
    """Endpoint parameter for operations whose rejections must not cost budget.

    Declare it before the session parameter so its headers reach every answer. It spends and
    rejects nothing itself: a request is judged on its preconditions first (401, 403, 412,
    428), and 429 comes only from `consume()` at the accept point.
    """

    async def dependency(request: Request) -> RateBudget:
        subject = _budget_subject(request, policy)
        limiter: RateLimiter = request.app.state.rate_limiter
        decision = (
            await limiter.peek(policy, subject)
            if subject is not None
            else Decision(True, policy.quota, 0, None)
        )
        _publish(request, policy, decision)
        return RateBudget(request, policy, subject, limiter)

    return dependency


def rate_limit(policy: RatePolicy) -> Callable[[Request], Awaitable[None]]:
    """Route dependency: `dependencies=[Depends(rate_limit(UPLOADS_CREATE))]`.

    Put it in the route's `dependencies` so it runs before authentication and its headers
    reach 401 and 403 answers too.
    """

    async def dependency(request: Request) -> None:
        subject = _budget_subject(request, policy)
        if subject is None:
            decision = Decision(True, policy.quota, 0, None)
        else:
            limiter: RateLimiter = request.app.state.rate_limiter
            decision = await limiter.hit(policy, subject)
        _publish(request, policy, decision)
        if not decision.allowed:
            raise _rate_limited(decision)

    return dependency


def cookie_subject(cookie: str) -> str:
    """Budget key of a session cookie (the session itself is resolved only after the limit)."""
    return "s:" + hashlib.sha256(cookie.encode()).hexdigest()[:32]


def _budget_subject(request: Request, policy: RatePolicy) -> str | None:
    """Budget key; None when nothing is spent: limits switched off, or a session policy
    without a cookie (authentication answers 401 before any database work)."""
    if not request.app.state.settings.rate_limits_enabled:
        return None
    if policy.subject is Subject.IP:
        return "ip:" + client_network(request)
    # A forged cookie spends its own budget and then gets 401.
    cookie = request.cookies.get(SESSION_COOKIE)
    return cookie_subject(cookie) if cookie else None


def _publish(request: Request, policy: RatePolicy, decision: Decision) -> None:
    setattr(
        request.state,
        RATE_LIMIT_HEADERS_STATE,
        {
            "RateLimit-Policy": policy.header,
            "RateLimit": f'"{policy.name}";r={decision.remaining};t={decision.reset_s}',
        },
    )


def _rate_limited(decision: Decision) -> ProblemError:
    return ProblemError(ErrorCode.RATE_LIMITED, headers={"Retry-After": str(decision.reset_s)})


def _key(policy: RatePolicy, subject: str) -> str:
    return f"rl:{policy.name}:{subject}"


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def client_network(request: Request) -> str:
    """Client address; IPv6 clients are grouped by /64 (06-api-contract, section 7)."""
    address = client_ip(request)
    if address is None:
        return "unknown"
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)
