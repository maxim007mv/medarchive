import io
import os
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.transaction import workspace_tx
from app.storage.s3 import ObjectStorage, StorageUnavailableError
from app.workers.purge import Purger, PurgeReport

pytestmark = pytest.mark.usefixtures("storage")


async def _create_workspace(app_sessions: async_sessionmaker[AsyncSession]) -> UUID:
    workspace_id = uuid4()
    async with app_sessions() as db, workspace_tx(db, workspace_id):
        await db.execute(
            text("SELECT app.create_workspace(:dek, 'k1', '2026-11-10', :evidence)"),
            {"dek": os.urandom(64), "evidence": os.urandom(32)},
        )
    return workspace_id


async def _add_document(
    superuser: AsyncEngine,
    storage: ObjectStorage,
    workspace_id: UUID,
    *,
    deleted_ago: timedelta | None,
) -> str:
    document_id = uuid4()
    key = f"ws/{workspace_id}/{document_id}.bin"
    storage.docs.upload(key, io.BytesIO(b"ciphertext"))
    async with superuser.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.documents (id, workspace_id, type_code, title_ct, title_bidx,"
                " deleted_at) VALUES (:id, :ws, 'analysis', :ct, ARRAY[1]::bigint[],"
                " CASE WHEN CAST(:ago AS interval) IS NULL THEN NULL ELSE now() - :ago END)"
            ),
            {"id": document_id, "ws": workspace_id, "ct": os.urandom(40), "ago": deleted_ago},
        )
        await connection.execute(
            text(
                "INSERT INTO app.document_files (document_id, workspace_id, object_key, size_bytes,"
                " sha256, original_name_ct) VALUES (:id, :ws, :key, 10, :sha, :name)"
            ),
            {"id": document_id, "ws": workspace_id, "key": key, "sha": bytes(32), "name": b"n"},
        )
    return key


async def _scalar(superuser: AsyncEngine, sql: str, **params: object) -> object:
    async with superuser.connect() as connection:
        return (await connection.execute(text(sql), params)).scalar()


@pytest.fixture
async def purger(
    worker_sessions: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> Purger:
    # MinIO stamps objects with the current time; the orphan age is tested in test_purge_rules.
    monkeypatch.setattr("app.workers.purge.ORPHAN_MIN_AGE", timedelta(0))
    return Purger(worker_sessions, storage)


async def test_purge_removes_only_what_is_due_and_is_idempotent(
    app_sessions: async_sessionmaker[AsyncSession],
    superuser_engine: AsyncEngine,
    storage: ObjectStorage,
    purger: Purger,
) -> None:
    workspace_id = await _create_workspace(app_sessions)
    old_deleted = await _add_document(
        superuser_engine, storage, workspace_id, deleted_ago=timedelta(hours=25)
    )
    fresh_deleted = await _add_document(
        superuser_engine, storage, workspace_id, deleted_ago=timedelta(hours=1)
    )
    live = await _add_document(superuser_engine, storage, workspace_id, deleted_ago=None)
    orphan = f"ws/{workspace_id}/{uuid4()}.bin"
    storage.docs.upload(orphan, io.BytesIO(b"left by a failed transaction"))
    upload_key = f"q/{workspace_id}/{uuid4()}.bin"
    storage.quarantine.upload(upload_key, io.BytesIO(b"%PDF-"))
    async with superuser_engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.uploads (id, workspace_id, quarantine_key, max_bytes, created_at,"
                " expires_at) VALUES (:id, :ws, :key, 20971520, now() - interval '26 hours',"
                " now() - interval '25 hours')"
            ),
            {"id": uuid4(), "ws": workspace_id, "key": upload_key},
        )
        await connection.execute(
            text(
                "INSERT INTO app.exports (id, workspace_id, scope, document_ids, total_bytes,"
                " created_at, expires_at) VALUES (:id, :ws, 'all', ARRAY[:doc]::uuid[], 10,"
                " now() - interval '2 hours', now() - interval '1 hour')"
            ),
            {"id": uuid4(), "ws": workspace_id, "doc": uuid4()},
        )
        await connection.execute(
            text(
                "INSERT INTO app.idempotency_keys (workspace_id, key, operation, fingerprint,"
                " expires_at) VALUES (:ws, :key, 'uploads.create', :fp, now() - interval '1 hour')"
            ),
            {"ws": workspace_id, "key": "k" * 16, "fp": bytes(32)},
        )

    report = await purger.run_once()

    # Other tests share the database: count only this workspace's rows.
    assert min(report.documents, report.uploads, report.exports, report.idempotency_keys) >= 1
    assert report.orphans >= 1
    assert storage.docs.size(old_deleted) is None
    assert storage.docs.size(orphan) is None
    assert storage.quarantine.size(upload_key) is None
    assert storage.docs.size(fresh_deleted) == len(b"ciphertext")
    assert storage.docs.size(live) == len(b"ciphertext")
    remaining = {
        "SELECT count(*) FROM app.documents WHERE workspace_id = :ws": 2,
        "SELECT count(*) FROM app.uploads WHERE workspace_id = :ws": 0,
        "SELECT count(*) FROM app.exports WHERE workspace_id = :ws": 0,
        "SELECT count(*) FROM app.idempotency_keys WHERE workspace_id = :ws": 0,
    }
    for query, expected in remaining.items():
        assert await _scalar(superuser_engine, query, ws=workspace_id) == expected, query
    purge_audit = (
        "SELECT count(*) FROM app.audit_log WHERE workspace_id = :ws AND action = 'document.purge'"
    )
    assert await _scalar(superuser_engine, purge_audit, ws=workspace_id) == 1

    again = await purger.run_once()

    assert again == PurgeReport()


async def test_purge_deletes_a_workspace_after_purge_after(
    app_sessions: async_sessionmaker[AsyncSession],
    superuser_engine: AsyncEngine,
    storage: ObjectStorage,
    purger: Purger,
) -> None:
    workspace_id = await _create_workspace(app_sessions)
    document_key = await _add_document(superuser_engine, storage, workspace_id, deleted_ago=None)
    quarantine_key = f"q/{workspace_id}/{uuid4()}.bin"
    storage.quarantine.upload(quarantine_key, io.BytesIO(b"%PDF-"))
    async with app_sessions() as db, workspace_tx(db, workspace_id):
        await db.execute(text("SELECT app.delete_workspace()"))
    async with superuser_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE app.workspaces SET deleted_at = now() - interval '25 hours',"
                " purge_after = now() - interval '1 hour' WHERE id = :ws"
            ),
            {"ws": workspace_id},
        )

    report = await purger.run_once()

    assert report.workspaces == 1
    assert storage.docs.size(document_key) is None
    assert storage.quarantine.size(quarantine_key) is None
    exists = "SELECT count(*) FROM app.workspaces WHERE id = :ws"
    assert await _scalar(superuser_engine, exists, ws=workspace_id) == 0
    files = "SELECT count(*) FROM app.document_files WHERE workspace_id = :ws"
    assert await _scalar(superuser_engine, files, ws=workspace_id) == 0


async def test_purge_keeps_audit_partitions_ahead(
    superuser_engine: AsyncEngine, purger: Purger
) -> None:
    await purger.run_once()

    partitions = (
        "SELECT count(*) FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid"
        " WHERE i.inhparent = 'app.audit_log'::regclass AND c.relname ~ '^audit_log_[0-9]{4}_'"
        " AND to_date(substr(c.relname, 11), 'YYYY_MM') >= date_trunc('month', now())"
    )
    assert await _scalar(superuser_engine, partitions) == 3


async def test_workspace_row_goes_even_if_storage_cannot_list(
    app_sessions: async_sessionmaker[AsyncSession],
    superuser_engine: AsyncEngine,
    purger: Purger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = await _create_workspace(app_sessions)
    async with app_sessions() as db, workspace_tx(db, workspace_id):
        await db.execute(text("SELECT app.delete_workspace()"))
    async with superuser_engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE app.workspaces SET purge_after = now() - interval '1 hour' WHERE id = :ws"
            ),
            {"ws": workspace_id},
        )

    def unavailable(bucket: object, prefix: str) -> list[str]:
        raise StorageUnavailableError

    monkeypatch.setattr("app.storage.s3.Bucket.list", unavailable)

    report = await purger.run_once()

    assert report.storage_failures >= 2
    exists = "SELECT count(*) FROM app.workspaces WHERE id = :ws"
    assert await _scalar(superuser_engine, exists, ws=workspace_id) == 0
