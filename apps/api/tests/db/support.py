from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

API_DIR = Path(__file__).resolve().parents[2]
DATABASE = "medarchive"


@dataclass(frozen=True)
class Cluster:
    version: str
    host: str
    port: int
    passwords: dict[str, str]

    def url(self, role: str, database: str = DATABASE) -> str:
        password = self.passwords[role]
        return f"postgresql+asyncpg://{role}:{password}@{self.host}:{self.port}/{database}"


@dataclass(frozen=True)
class Sessions:
    app: async_sessionmaker[AsyncSession]
    worker: async_sessionmaker[AsyncSession]
    superuser: async_sessionmaker[AsyncSession]


def alembic_upgrade(cluster: Cluster, database: str, revision: str = "head") -> None:
    command.upgrade(_alembic_config(cluster, database), revision)


def alembic_downgrade(cluster: Cluster, database: str, revision: str = "base") -> None:
    command.downgrade(_alembic_config(cluster, database), revision)


def _alembic_config(cluster: Cluster, database: str) -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", cluster.url("ma_owner", database))
    return config


async def create_database(cluster: Cluster, name: str) -> None:
    """Empty database prepared the way 01-roles.sh prepares `medarchive`."""
    engine = create_async_engine(
        cluster.url("postgres"), poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    async with engine.connect() as connection:
        for statement in (
            f'CREATE DATABASE "{name}" OWNER ma_owner',
            f'REVOKE ALL ON DATABASE "{name}" FROM PUBLIC',
            f'GRANT CONNECT ON DATABASE "{name}" TO ma_app, ma_worker',
        ):
            await connection.exec_driver_sql(statement)
    await engine.dispose()


def sqlstate(error: DBAPIError) -> str | None:
    state: str | None = getattr(error.orig, "sqlstate", None)
    return state


INSUFFICIENT_PRIVILEGE = "42501"
