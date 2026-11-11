"""Schema tests on real PostgreSQL 17 and 18 (testcontainers, Docker required).

Each server is initialised by the real infra/postgres/init/01-roles.sh, so roles, passwords and
memberships are those of docker compose; migrations run as ma_owner exactly like `migrate`.
"""

import asyncio
import os
import secrets
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

from app.db.engine import create_sessionmaker
from app.db.models import Document
from app.db.transaction import workspace_tx
from db.support import API_DIR, DATABASE, Cluster, Sessions, alembic_upgrade

ROLES_INIT_DIR = API_DIR.parents[1] / "infra" / "postgres" / "init"
IMAGES = {"17": "postgres:17-alpine", "18": "postgres:18-alpine"}
LOGIN_ROLES = ("postgres", "ma_owner", "ma_app", "ma_worker")

CREATE_WORKSPACE = text(
    "SELECT app.create_workspace(:dek, 'kek-1', '2026-11-10', :evidence) AS created_at"
)


@pytest.fixture(scope="session", params=sorted(IMAGES), ids=lambda version: f"pg{version}")
def cluster(request: pytest.FixtureRequest) -> Iterator[Cluster]:
    version: str = request.param
    passwords = {role: secrets.token_hex(16) for role in LOGIN_ROLES}
    container = (
        PostgresContainer(
            IMAGES[version],
            username="postgres",
            password=passwords["postgres"],
            dbname=DATABASE,
            driver=None,
        )
        .with_env("MA_OWNER_PASSWORD", passwords["ma_owner"])
        .with_env("MA_APP_PASSWORD", passwords["ma_app"])
        .with_env("MA_WORKER_PASSWORD", passwords["ma_worker"])
        .with_volume_mapping(str(ROLES_INIT_DIR), "/docker-entrypoint-initdb.d", "ro")
    )
    with container:
        yield Cluster(
            version=version,
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(5432)),
            passwords=passwords,
        )


@pytest.fixture(scope="session")
def migrated(cluster: Cluster) -> Cluster:
    alembic_upgrade(cluster, DATABASE)
    return cluster


@pytest.fixture
async def sessions(migrated: Cluster) -> AsyncIterator[Sessions]:
    engines = {
        role: create_async_engine(migrated.url(role), poolclass=NullPool)
        for role in ("ma_app", "ma_worker", "postgres")
    }
    yield Sessions(
        app=create_sessionmaker(engines["ma_app"]),
        worker=create_sessionmaker(engines["ma_worker"]),
        superuser=create_sessionmaker(engines["postgres"]),
    )
    await asyncio.gather(*(engine.dispose() for engine in engines.values()))


@pytest.fixture
def make_workspace(sessions: Sessions) -> Callable[[], Awaitable[uuid.UUID]]:
    """Creates a workspace the way POST /workspaces does: id from the app, rows via 0002."""

    async def make() -> uuid.UUID:
        workspace_id = uuid.uuid4()
        async with sessions.app() as session, workspace_tx(session, workspace_id):
            await session.execute(
                CREATE_WORKSPACE, {"dek": os.urandom(64), "evidence": os.urandom(32)}
            )
        return workspace_id

    return make


@pytest.fixture
def make_document(sessions: Sessions) -> Callable[[uuid.UUID], Awaitable[uuid.UUID]]:
    async def make(workspace_id: uuid.UUID) -> uuid.UUID:
        document = Document(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            type_code="other",
            title_ct=os.urandom(40),
            title_bidx=[1],
        )
        async with sessions.app() as session, workspace_tx(session, workspace_id):
            session.add(document)
        return document.id

    return make
