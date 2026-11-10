from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.core import health
from app.core.config import Settings, get_settings
from app.core.crypto import Kek
from app.core.errors import install_error_handlers
from app.core.middleware import RequestContextMiddleware
from app.core.observability import configure_logging, configure_sentry
from app.core.page_token import PageTokenCodec
from app.core.ratelimit import RateLimiter
from app.db.engine import create_engine, create_sessionmaker
from app.modules.auth.router import router as auth_router
from app.modules.workspace.router import router as workspace_router
from app.storage.s3 import ObjectStorage


def create_app(settings: Settings | None = None) -> FastAPI:
    """Settings are read at startup, so importing the module needs no environment."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        config = settings or get_settings()
        configure_logging(config.log_level)
        configure_sentry(config.sentry_dsn, config.environment)
        redis = Redis.from_url(config.redis_url)
        engine = create_engine(config.database_url)
        app.state.settings = config
        app.state.kek = Kek.from_file(config.kek_keyset_path)
        app.state.db_engine = engine
        app.state.db_sessions = create_sessionmaker(engine)
        app.state.storage = ObjectStorage.from_settings(config)
        app.state.rate_limiter = RateLimiter(redis)
        app.state.page_tokens = PageTokenCodec(
            [
                secret.get_secret_value()
                for secret in (config.page_token_key, config.page_token_key_previous)
                if secret is not None
            ]
        )
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    # Swagger UI and ReDoc load scripts from external CDNs, which AGENTS.md forbids.
    app = FastAPI(title="Медархив API", docs_url=None, redoc_url=None, lifespan=lifespan)
    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(auth_router)
    app.include_router(workspace_router)
    return app


app = create_app()
