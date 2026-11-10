"""Liveness, readiness (BE-01) and Prometheus exposition. Outside `/api/v1` and rate limits."""

import asyncio
from collections.abc import Awaitable, Callable

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.responses import Response

from app.core.crypto import Kek
from app.core.metrics import metrics_response
from app.storage.s3 import ObjectStorage

CHECK_TIMEOUT_S = 3.0
_READINESS_PROBE_KEY = "readyz/probe"

router = APIRouter(tags=["health"])
log = structlog.get_logger("app.health")


@router.get("/healthz", operation_id="health.live")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/readyz",
    operation_id="health.ready",
    responses={503: {"description": "Не готов"}},
)
async def readyz(request: Request) -> JSONResponse:
    checks: dict[str, Callable[[], Awaitable[None]]] = {
        "db": lambda: _check_db(request),
        "storage": lambda: _check_storage(request),
        "kek": lambda: _check_kek(request),
    }
    results = dict(
        zip(
            checks,
            await asyncio.gather(*(_run(name, check) for name, check in checks.items())),
            strict=True,
        )
    )
    ready = all(result == "ok" for result in results.values())
    return JSONResponse(
        {"status": "ok" if ready else "unavailable", "checks": results},
        status_code=200 if ready else 503,
    )


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return metrics_response()


async def _run(name: str, check: Callable[[], Awaitable[None]]) -> str:
    try:
        await asyncio.wait_for(check(), CHECK_TIMEOUT_S)
    except Exception as exc:  # any failure means "not ready"; the type is enough to diagnose
        log.warning("readiness_check_failed", check=name, error_type=type(exc).__name__)
        return "unavailable"
    return "ok"


async def _check_db(request: Request) -> None:
    async with request.app.state.db_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _check_storage(request: Request) -> None:
    # The API user may only touch objects (infra/minio/api-policy.json), so HEAD of a missing
    # object is the cheapest call that proves both endpoint and credentials work.
    storage: ObjectStorage = request.app.state.storage
    for bucket in (storage.quarantine, storage.docs):
        await asyncio.to_thread(bucket.size, _READINESS_PROBE_KEY)


async def _check_kek(request: Request) -> None:
    await asyncio.to_thread(Kek.from_file, request.app.state.settings.kek_keyset_path)
