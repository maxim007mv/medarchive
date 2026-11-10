"""Prometheus metrics (BE-15). Labels never carry user data: routes are path templates."""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests by route template and status",
    ["method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "route"]
)
UPLOAD_BYTES = Histogram(
    "upload_bytes",
    "Size of accepted PDF uploads",
    buckets=(10_000, 100_000, 500_000, 1_000_000, 5_000_000, 10_000_000, 20_971_520),
)
S3_ERRORS = Counter("s3_errors_total", "Object storage errors by operation", ["operation"])


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
