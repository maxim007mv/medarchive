# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.7 AS uv

FROM python:3.12-slim-bookworm AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev
COPY . .

FROM python:3.12-slim-bookworm
RUN useradd --system --uid 10001 --no-create-home api
WORKDIR /app
COPY --from=build /app /app
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER api
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
# Python is CPU-bound per request (~8 ms list, ~17 ms search at 1000 docs): several processes on
# SO_REUSEPORT sockets keep k6 p95 < 300 ms at 50 VU (DoD 4). Each has its own DB pool (DB-12).
# Two malloc arenas: thread pools otherwise grow each process's RSS by an arena per thread.
ENV WEB_CONCURRENCY=4 MALLOC_ARENA_MAX=2
CMD ["python", "-m", "app.serve"]
