"""DB-01: upgrade head on an empty database, downgrade base removes everything, repeatable."""

import asyncio
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from db.support import Cluster, alembic_downgrade, alembic_upgrade, create_database

_STATE = text(
    """SELECT
  (SELECT count(*) FROM pg_namespace WHERE nspname = 'app') AS app_schema,
  (SELECT count(*) FROM pg_extension
   WHERE extname IN ('pg_trgm', 'pgcrypto', 'btree_gin') AND extnamespace = 'public'::regnamespace)
    AS extensions,
  (SELECT array_agg(tablename::text ORDER BY tablename) FROM pg_tables WHERE schemaname = 'public')
    AS public_tables,
  (SELECT version_num FROM public.alembic_version) AS revision"""
)
_HEAD_ONLY = text(
    """SELECT
  (SELECT count(*) FROM app.document_types) AS document_types,
  has_schema_privilege('ma_auth', 'app', 'CREATE') AS auth_can_create"""
)


async def _state(cluster: Cluster, database: str, *, at_head: bool) -> dict[str, Any]:
    engine = create_async_engine(cluster.url("postgres", database), poolclass=NullPool)
    async with engine.connect() as connection:
        state = dict((await connection.execute(_STATE)).one()._mapping)
        if at_head:
            state |= (await connection.execute(_HEAD_ONLY)).one()._mapping
    await engine.dispose()
    return state


def test_db01_upgrade_downgrade_upgrade_on_empty_database(cluster: Cluster) -> None:
    database = "migration_cycle"
    asyncio.run(create_database(cluster, database))
    head = {
        "app_schema": 1,
        "extensions": 3,
        "public_tables": ["alembic_version"],
        "revision": "0003_workspace_timezone",
        "document_types": 3,
        "auth_can_create": False,
    }

    alembic_upgrade(cluster, database)
    after_upgrade = asyncio.run(_state(cluster, database, at_head=True))
    alembic_downgrade(cluster, database)
    after_downgrade = asyncio.run(_state(cluster, database, at_head=False))
    alembic_upgrade(cluster, database)
    after_second_upgrade = asyncio.run(_state(cluster, database, at_head=True))

    assert after_upgrade == head
    assert after_downgrade == {
        "app_schema": 0,
        "extensions": 0,
        "public_tables": ["alembic_version"],
        "revision": None,
    }
    assert after_second_upgrade == head
