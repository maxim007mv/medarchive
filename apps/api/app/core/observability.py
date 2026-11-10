"""JSON logs and Sentry without personal data (05-architecture, section 9; T8)."""

import logging
import sys
from typing import Any

import sentry_sdk
import structlog

SCRUBBED = "[scrubbed]"


def configure_logging(level: str) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level, force=True)
    # Uvicorn access lines contain the raw query string (`q=` is a search over medical titles);
    # RequestContextMiddleware writes its own line with the route template instead.
    logging.getLogger("uvicorn.access").disabled = True
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def configure_sentry(dsn: str, environment: str) -> None:
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        before_send=scrub_event,
        before_breadcrumb=lambda _crumb, _hint: None,
    )


def scrub_event(event: Any, _hint: Any) -> Any:
    """Keep only what locates a failure: exception types, frames, method and route."""
    request = event.get("request")
    if request:
        event["request"] = {
            "method": request.get("method"),
            "url": request.get("url", "").split("?")[0],
        }
    for exception in event.get("exception", {}).get("values", []):
        exception["value"] = SCRUBBED
        for frame in exception.get("stacktrace", {}).get("frames", []):
            frame.pop("vars", None)
    for key in ("user", "extra", "breadcrumbs", "contexts", "logentry"):
        event.pop(key, None)
    return event
