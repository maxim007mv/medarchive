"""Plans of the SQL the API itself builds (repository.py), on the DB-05 seed: one workspace of
10 000 documents among 2000 of 100, under ma_app and RLS. test_db_plans pins the reference
queries Q1..Q7; this file checks that the application's queries stay on the same indexes.
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.engine import create_sessionmaker
from app.db.transaction import workspace_tx
from app.modules.documents import repository
from app.modules.documents.listing import ListFilter
from db.support import Cluster, alembic_upgrade, create_database

DATABASE = "app_queries"
SEED = Path(__file__).with_name("seed_plans.sql")
TZ = "Europe/Moscow"
# The seed has no files; the list joins document_files for the size.
SEED_FILES = """INSERT INTO app.document_files
  (document_id, workspace_id, object_key, size_bytes, sha256, original_name_ct)
SELECT id, workspace_id, 'ws/' || workspace_id || '/' || id || '.bin', 1000,
  sha256(id::text::bytea), '\\x00'
FROM app.documents"""


@dataclass(frozen=True)
class Seed:
    cluster: Cluster
    heavy: uuid.UUID
    search_hashes: list[int]


async def _seed(cluster: Cluster) -> Seed:
    engine = create_async_engine(
        cluster.url("postgres", DATABASE), poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    async with engine.connect() as connection:
        asyncpg_connection = (await connection.get_raw_connection()).driver_connection
        assert asyncpg_connection is not None
        await asyncpg_connection.execute(SEED.read_text())
        await connection.exec_driver_sql(SEED_FILES)
        await connection.exec_driver_sql("VACUUM ANALYZE")
        info = (
            await connection.execute(text("SELECT heavy, search_hashes FROM public.seed_info"))
        ).one()
    await engine.dispose()
    return Seed(cluster, info.heavy, list(info.search_hashes))


@pytest.fixture(scope="session")
def seed(cluster: Cluster) -> Seed:
    asyncio.run(create_database(cluster, DATABASE))
    alembic_upgrade(cluster, DATABASE)
    return asyncio.run(_seed(cluster))


Query = Callable[[AsyncSession, uuid.UUID, Seed], Awaitable[Any]]


async def _explain(seed: Seed, query: Query) -> dict[str, Any]:
    """Run `query` as the API does, then EXPLAIN ANALYZE the statement it sent."""
    engine = create_async_engine(seed.cluster.url("ma_app", DATABASE), poolclass=NullPool)
    sent: list[tuple[str, Any]] = []

    def capture(_conn: Any, _cursor: Any, statement: str, parameters: Any, *_: Any) -> None:
        sent.append((statement, parameters))

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    async with create_sessionmaker(engine)() as session, workspace_tx(session, seed.heavy):
        await query(session, seed.heavy, seed)
        statement, parameters = sent[-1]
        explain = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement
        output = (await session.connection()).exec_driver_sql(explain, parameters)
        plan: dict[str, Any] = (await output).scalar_one()[0]
    await engine.dispose()
    return plan


def _nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    return [node, *(child for plan in node.get("Plans", []) for child in _nodes(plan))]


def _list(list_filter: ListFilter, order_by: Any = "document_date desc") -> Query:
    async def run(session: AsyncSession, workspace_id: uuid.UUID, _: Seed) -> Any:
        return await repository.list_matching(
            session, workspace_id, list_filter, TZ, order_by, limit=51
        )

    return run


def _count(list_filter: ListFilter) -> Query:
    async def run(session: AsyncSession, workspace_id: uuid.UUID, _: Seed) -> Any:
        return await repository.count_documents(session, workspace_id, list_filter, TZ)

    return run


async def _search(session: AsyncSession, workspace_id: uuid.UUID, seed: Seed) -> Any:
    return await repository.search_candidates(
        session, workspace_id, ListFilter(query="анализ"), TZ, seed.search_hashes
    )


# The seed puts document dates on a few days; 2024-12-31 is one of them.
DECEMBER = ListFilter(date_from=date(2024, 12, 1), date_to=date(2024, 12, 31))
QUERIES: dict[str, Query] = {
    "list": _list(ListFilter()),
    "list_by_upload": _list(ListFilter(), "uploaded_at desc"),
    "list_document_period": _list(DECEMBER),
    "list_document_until": _list(ListFilter(date_to=date(2024, 12, 31))),
    "list_upload_period": _list(replace(DECEMBER, date_field="uploaded")),
    "list_type": _list(ListFilter(types=("conclusion",))),
    "list_undated": _list(ListFilter(undated=True)),
    "count": _count(ListFilter()),
    "count_document_period": _count(DECEMBER),
    "count_type": _count(ListFilter(types=("conclusion",))),
    "search": _search,
}


@pytest.mark.parametrize("name", sorted(QUERIES))
async def test_app_queries_never_scan_documents_sequentially(seed: Seed, name: str) -> None:
    plan = await _explain(seed, QUERIES[name])

    assert [node for node in _nodes(plan["Plan"]) if node["Node Type"] == "Seq Scan"] == []


@pytest.mark.parametrize(
    ("name", "fragment"),
    [
        ("list_document_period", "list_key <="),
        ("list_document_until", "list_key >="),
        ("list_undated", "list_key = 2147483647"),
    ],
)
async def test_document_date_filters_are_ranges_of_documents_list(
    seed: Seed, name: str, fragment: str
) -> None:
    plan = await _explain(seed, QUERIES[name])
    scan = next(node for node in _nodes(plan["Plan"]) if node.get("Index Name") == "documents_list")

    assert scan["Actual Rows"] > 0
    assert fragment in scan["Index Cond"]
    assert scan.get("Rows Removed by Filter", 0) == 0
