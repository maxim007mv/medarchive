"""DB-05, DB-06: plans of Q1..Q7 under ma_app and RLS match db/explain-analyze.txt node by node.

Q4 follows ADR-046: Bitmap Index Scan on documents_title_bidx with workspace_id in Index Cond and
`title_bidx @>` in the Filter of the Bitmap Heap Scan (arraycontains is not LEAKPROOF, so under
FORCE ROW LEVEL SECURITY it is not pushed into the index ahead of the policy quals).
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.db.engine import create_sessionmaker
from app.db.transaction import workspace_tx
from db.support import Cluster, alembic_upgrade, create_database

DATABASE = "plans"
SEED = Path(__file__).with_name("seed_plans.sql")
MSK = timezone(timedelta(hours=3))


def _list_key(day: date) -> int:
    return (date(1900, 1, 1) - day).days


Q1 = """SELECT id, type_code, title_ct, document_date, uploaded_at, version,
  note_ct IS NOT NULL AS has_note
FROM app.documents WHERE workspace_id = :workspace_id AND deleted_at IS NULL
ORDER BY list_key, uploaded_at, id LIMIT 51"""
QUERIES = {
    "Q1": Q1,
    "Q2": """SELECT id, type_code, title_ct, document_date, uploaded_at, version
FROM app.documents WHERE workspace_id = :workspace_id AND deleted_at IS NULL
  AND (list_key, uploaded_at, id) > (:list_key, :uploaded_at, :after_id)
ORDER BY list_key, uploaded_at, id LIMIT 51""",
    "Q3": """SELECT count(*) FILTER (WHERE list_key <> 2147483647) AS matched,
  count(*) FILTER (WHERE list_key = 2147483647) AS undated_excluded
FROM app.documents WHERE workspace_id = :workspace_id AND deleted_at IS NULL
  AND (list_key BETWEEN :first AND :last OR list_key = 2147483647)""",
    "Q4": """SELECT id, title_ct FROM app.documents
WHERE workspace_id = :workspace_id AND deleted_at IS NULL AND title_bidx @> :hashes
ORDER BY list_key, uploaded_at, id LIMIT 51""",
    "Q5": """SELECT id, document_date, uploaded_at FROM app.documents
WHERE workspace_id = :workspace_id AND deleted_at IS NULL
  AND uploaded_at >= CAST(:date_from AS date)::timestamp AT TIME ZONE 'Europe/Moscow'
  AND uploaded_at < (CAST(:date_to AS date) + 1)::timestamp AT TIME ZONE 'Europe/Moscow'
ORDER BY uploaded_at, id LIMIT 51""",
    "Q6": """SELECT id, uploaded_at FROM app.documents
WHERE workspace_id = :workspace_id AND deleted_at IS NULL AND list_key = 2147483647
ORDER BY list_key, uploaded_at, id LIMIT 51""",
    "Q7": Q1,
}
PARAMS: dict[str, dict[str, Any]] = {
    "Q2": {
        "list_key": _list_key(date(2025, 6, 1)),
        "uploaded_at": datetime(2025, 6, 1, 10, tzinfo=MSK),
        "after_id": uuid.UUID(int=0),
    },
    "Q3": {"first": _list_key(date(2025, 4, 30)), "last": _list_key(date(2025, 4, 1))},
    # Day boundaries in SQL, as 07-database section 4 prescribes: with precomputed timestamptz
    # values the planner switches to Bitmap Heap Scan + Sort.
    "Q5": {"date_from": date(2025, 4, 1), "date_to": date(2025, 4, 30)},
}

# Node chain along the first child, as in db/explain-analyze.txt.
EXPECTED = {
    "Q1": ["Limit", "Result", "Index Scan documents_list"],
    "Q2": ["Limit", "Result", "Index Scan documents_list"],
    "Q3": ["Aggregate", "Result", "Index Only Scan documents_list"],
    "Q4": [
        "Limit",
        "Sort",
        "Result",
        "Bitmap Heap Scan",
        "Bitmap Index Scan documents_title_bidx",
    ],
    "Q5": ["Limit", "Result", "Index Scan documents_by_upload"],
    "Q6": ["Limit", "Result", "Index Only Scan documents_list"],
    "Q7": ["Limit", "Result", "Index Scan documents_list"],
}


@dataclass(frozen=True)
class Seed:
    cluster: Cluster
    heavy: uuid.UUID
    normal: uuid.UUID
    search_hashes: list[int]


async def _seed(cluster: Cluster) -> Seed:
    engine = create_async_engine(
        cluster.url("postgres", DATABASE), poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    async with engine.connect() as connection:
        asyncpg_connection = (await connection.get_raw_connection()).driver_connection
        assert asyncpg_connection is not None
        # The simple query protocol of asyncpg runs the multi-statement script in one go.
        await asyncpg_connection.execute(SEED.read_text())
        await connection.exec_driver_sql("VACUUM ANALYZE")
        info = (
            await connection.execute(
                text("SELECT heavy, normal, search_hashes FROM public.seed_info")
            )
        ).one()
    await engine.dispose()
    return Seed(cluster, info.heavy, info.normal, list(info.search_hashes))


@pytest.fixture(scope="session")
def seed(cluster: Cluster) -> Seed:
    asyncio.run(create_database(cluster, DATABASE))
    alembic_upgrade(cluster, DATABASE)
    return asyncio.run(_seed(cluster))


async def _plan(seed: Seed, query: str) -> dict[str, Any]:
    workspace_id = seed.normal if query == "Q7" else seed.heavy
    params = {**PARAMS.get(query, {}), "workspace_id": workspace_id}
    if query == "Q4":
        # A literal array from the application, never a subquery (DB-06).
        params["hashes"] = seed.search_hashes
    engine = create_async_engine(seed.cluster.url("ma_app", DATABASE), poolclass=NullPool)
    async with create_sessionmaker(engine)() as session, workspace_tx(session, workspace_id):
        explain = text("EXPLAIN (FORMAT JSON) " + QUERIES[query])
        output = (await session.execute(explain, params)).scalar_one()
    await engine.dispose()
    # asyncpg decodes the json column already.
    plan: dict[str, Any] = output[0]["Plan"]
    return plan


def _chain(node: dict[str, Any]) -> list[str]:
    labels = []
    while True:
        index = node.get("Index Name")
        labels.append(f"{node['Node Type']} {index}" if index else node["Node Type"])
        if "Plans" not in node:
            return labels
        node = node["Plans"][0]


def _leaf(plan: dict[str, Any]) -> dict[str, Any]:
    while "Plans" in plan:
        plan = plan["Plans"][0]
    return plan


def _node(plan: dict[str, Any], node_type: str) -> dict[str, Any]:
    while plan["Node Type"] != node_type:
        plan = plan["Plans"][0]
    return plan


@pytest.mark.parametrize("query", sorted(EXPECTED))
async def test_db05_plan_node_types_match_reference(seed: Seed, query: str) -> None:
    plan = await _plan(seed, query)

    assert _chain(plan) == EXPECTED[query]
    assert "workspace_id" in _leaf(plan)["Index Cond"]


@pytest.mark.parametrize(
    ("query", "node_type", "fragment"),
    [
        ("Q2", "Index Scan", "ROW(list_key, uploaded_at, id) > ROW("),
        ("Q5", "Index Scan", "uploaded_at >="),
        ("Q6", "Index Only Scan", "list_key = 2147483647"),
    ],
)
async def test_db05_range_conditions_are_index_conditions(
    seed: Seed, query: str, node_type: str, fragment: str
) -> None:
    plan = await _plan(seed, query)

    assert fragment in _node(plan, node_type)["Index Cond"]
    assert "Filter" not in _node(plan, node_type)


async def test_db06_blind_index_search_filters_by_workspace_in_index_and_trigrams_after(
    seed: Seed,
) -> None:
    plan = await _plan(seed, "Q4")
    heap, index = _node(plan, "Bitmap Heap Scan"), _node(plan, "Bitmap Index Scan")

    assert "workspace_id" in index["Index Cond"]
    assert "title_bidx" not in index["Index Cond"]
    assert "title_bidx @>" in heap["Filter"]
