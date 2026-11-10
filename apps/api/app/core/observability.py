"""JSON logs and Sentry without personal data (05-architecture, section 9; T8)."""

import logging
import sys
from typing import Any

import sentry_sdk
import structlog

SCRUBBED = "[scrubbed]"


# Their INFO lines carry full URLs, query strings included.
_URL_LOGGERS = ("httpx", "httpcore", "botocore", "boto3", "urllib3", "s3transfer")


def configure_logging(level: str) -> None:
    """One JSON line per event on stdout, for structlog and stdlib loggers alike."""
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(ensure_ascii=False),
            ],
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for name in _URL_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    # Uvicorn access lines contain the raw query string (`q=` is a search over medical titles);
    # RequestContextMiddleware writes its own line with the route template instead.
    logging.getLogger("uvicorn.access").disabled = True


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
