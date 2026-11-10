import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# DB-10: a migration fails instead of queueing behind live traffic.
MIGRATION_SETTINGS = {"lock_timeout": "3s", "statement_timeout": "60s"}

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _run(connection: Connection) -> None:
    # In public, not app: downgrade to base drops the app schema with everything in it.
    context.configure(connection=connection, version_table_schema="public")
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    url = config.get_main_option("sqlalchemy.url") or os.environ["DATABASE_URL"]
    engine = create_async_engine(
        url, poolclass=pool.NullPool, connect_args={"server_settings": MIGRATION_SETTINGS}
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("offline mode is not supported: migrations switch roles on a live connection")
asyncio.run(_run_online())
