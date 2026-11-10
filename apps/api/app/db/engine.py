from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# DB-12: pool of 10 per process, no overflow; a statement longer than 5 s is cancelled.
POOL_SIZE = 10
STATEMENT_TIMEOUT = "5s"


def create_engine(database_url: str) -> AsyncEngine:
    """Engine for a postgresql+asyncpg URL (ma_app for the API, ma_worker for the worker)."""
    return create_async_engine(
        database_url,
        pool_size=POOL_SIZE,
        max_overflow=0,
        connect_args={"server_settings": {"statement_timeout": STATEMENT_TIMEOUT}},
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # autobegin=False: a statement outside workspace_tx() or session.begin() raises instead of
    # silently running in a transaction without app.workspace_id.
    return async_sessionmaker(engine, expire_on_commit=False, autobegin=False)
