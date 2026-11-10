"""Throwaway PostgreSQL (roles from infra/postgres/init, migrations to head) and MinIO.

On Docker Desktop for macOS run with TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock:
the Ryuk reaper cannot mount ~/.docker/run/docker.sock.
"""

import os
import secrets
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

import boto3
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.community.minio import MinioContainer
from testcontainers.community.postgres import PostgresContainer

from app.db.engine import create_engine, create_sessionmaker
from app.storage.s3 import ObjectStorage

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT.parents[1]
MINIO_IMAGE = "pgsty/minio:RELEASE.2026-08-04T00-00-00Z"
POSTGRES_IMAGE = "postgres:17-alpine"
QUARANTINE_BUCKET, DOCS_BUCKET = "ma-quarantine", "ma-docs"
ROLES = ("ma_owner", "ma_app", "ma_worker")


@dataclass(frozen=True)
class DatabaseUrls:
    # Superuser bypasses RLS: tests use it only to arrange rows (backdate, inspect ciphertext).
    superuser: str
    owner: str
    app: str
    worker: str


@pytest.fixture(scope="session")
def storage() -> Iterator[ObjectStorage]:
    """Both buckets in a throwaway MinIO; the API credentials are the root user here."""
    with MinioContainer(image=MINIO_IMAGE) as minio:
        config = minio.get_config()
        endpoint = f"http://{config['endpoint']}"
        admin = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
            region_name="us-east-1",
        )
        for bucket in (QUARANTINE_BUCKET, DOCS_BUCKET):
            admin.create_bucket(Bucket=bucket)
        yield ObjectStorage(
            endpoint=endpoint,
            public_endpoint=endpoint,
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            quarantine_bucket=QUARANTINE_BUCKET,
            docs_bucket=DOCS_BUCKET,
        )


@pytest.fixture(scope="session")
def database() -> Iterator[DatabaseUrls]:
    passwords = {role: secrets.token_hex(16) for role in ROLES}
    container = (
        PostgresContainer(POSTGRES_IMAGE, dbname="medarchive", driver="asyncpg")
        .with_env("MA_OWNER_PASSWORD", passwords["ma_owner"])
        .with_env("MA_APP_PASSWORD", passwords["ma_app"])
        .with_env("MA_WORKER_PASSWORD", passwords["ma_worker"])
        .with_volume_mapping(
            str(REPO_ROOT / "infra/postgres/init"), "/docker-entrypoint-initdb.d", "ro"
        )
    )
    with container as postgres:
        host = postgres.get_container_host_ip()
        port = postgres.get_exposed_port(5432)

        def url(role: str, password: str) -> str:
            return f"postgresql+asyncpg://{role}:{password}@{host}:{port}/medarchive"

        urls = DatabaseUrls(
            superuser=url(postgres.username, postgres.password),
            owner=url("ma_owner", passwords["ma_owner"]),
            app=url("ma_app", passwords["ma_app"]),
            worker=url("ma_worker", passwords["ma_worker"]),
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=API_ROOT,
            env={**os.environ, "DATABASE_URL": urls.owner},
            check=True,
            timeout=120,
        )
        yield urls


@pytest.fixture
async def app_engine(database: DatabaseUrls) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(database.app)
    yield engine
    await engine.dispose()


@pytest.fixture
async def worker_engine(database: DatabaseUrls) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(database.worker)
    yield engine
    await engine.dispose()


@pytest.fixture
async def superuser_engine(database: DatabaseUrls) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(database.superuser)
    yield engine
    await engine.dispose()


@pytest.fixture
def app_sessions(app_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_sessionmaker(app_engine)


@pytest.fixture
def worker_sessions(worker_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_sessionmaker(worker_engine)
