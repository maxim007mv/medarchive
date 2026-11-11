"""Cleanup worker (BE-13, DB-09): physical deletion of what the API only marked or let expire.

Runs as ma_worker, which sees nothing without `app.workspace_id`: due workspaces come from
`app.workspaces_due_for_purge`, then each one is cleaned under its own RLS context. Every step
is idempotent (a missing object or row is not an error) and works in batches of 500, so a crash
or a second worker only repeats work. An object that storage refuses to delete goes to
`purge_queue` and is retried with backoff; its row is deleted anyway.

Entry point: `python -m app.workers.purge [--once]`.
"""

import argparse
import asyncio
import itertools
import signal
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

import structlog
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import CursorResult, Delete, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.observability import configure_logging
from app.db.engine import create_engine, create_sessionmaker
from app.db.models import (
    Document,
    DocumentFile,
    Export,
    IdempotencyKey,
    PurgeQueue,
    Upload,
    Workspace,
)
from app.db.transaction import workspace_tx
from app.storage.s3 import Bucket, ObjectStorage, StorageUnavailableError, StoredObject

BATCH_SIZE = 500
DELETED_DOCUMENT_GRACE = timedelta(hours=24)
# An expired upload still answers 410 upload_expired for a day, as long as its quarantine object
# lives (lifecycle rule of ma-quarantine), so the client learns why instead of seeing 404.
EXPIRED_UPLOAD_GRACE = timedelta(hours=24)
ORPHAN_MIN_AGE = timedelta(hours=1)
# Bound on due-workspace rounds per run, so a workspace that never empties cannot spin forever.
MAX_ROUNDS = 100
MAX_RETRY_DELAY = timedelta(hours=6)

# Plain INSERT: ma_worker has no SELECT on the journal, so no RETURNING of the identity key.
_INSERT_PURGE_AUDIT = text(
    "INSERT INTO app.audit_log (workspace_id, action, entity_id)"
    " VALUES (:workspace_id, 'document.purge', :entity_id)"
)

log = structlog.get_logger("app.workers.purge")


class WorkerSettings(BaseSettings):
    """The worker needs no KEK, CSRF or page token secrets: it never decrypts anything."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    database_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: SecretStr
    s3_bucket_quarantine: str = "ma-quarantine"
    s3_bucket_docs: str = "ma-docs"
    purge_interval_seconds: int = 300
    log_level: str = "INFO"


@dataclass
class PurgeReport:
    """Counts only: object keys and ids are not logged."""

    workspaces: int = 0
    documents: int = 0
    uploads: int = 0
    exports: int = 0
    idempotency_keys: int = 0
    workspace_create_keys: int = 0
    queued_objects: int = 0
    orphans: int = 0
    audit_partitions: int = 0
    failed_deletes: int = 0
    storage_failures: int = 0


class Purger:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], storage: ObjectStorage) -> None:
        self._sessions = sessions
        self._storage = storage

    async def run_once(self) -> PurgeReport:
        report = PurgeReport()
        async with self._sessions() as db, db.begin():
            report.audit_partitions = await db.scalar(text("SELECT app.ensure_audit_partitions()"))
        report.workspace_create_keys = await self._purge_workspace_create_keys()
        seen: set[UUID] = set()
        for _ in range(MAX_ROUNDS):
            due = await self._due_workspaces()
            if not due or seen.issuperset(due):
                break
            seen.update(due)
            for workspace_id in due:
                # Listing a bucket can fail; the workspace stays due and the next tick retries.
                with _storage_failure_logged("workspace", report):
                    await self._purge_workspace(workspace_id, report)
        with _storage_failure_logged("queue", report):
            await self._drain_queue(report)
        with _storage_failure_logged("orphans", report):
            await self._purge_orphans(report)
        return report

    async def _purge_workspace_create_keys(self) -> int:
        purged = 0
        while True:
            async with self._sessions() as db, db.begin():
                count: int = await db.scalar(
                    text("SELECT app.purge_expired_workspace_create_keys(:limit)"),
                    {"limit": BATCH_SIZE},
                )
            purged += count
            if count < BATCH_SIZE:
                return purged

    async def _due_workspaces(self) -> list[UUID]:
        async with self._sessions() as db, db.begin():
            rows = await db.execute(
                text("SELECT workspace_id FROM app.workspaces_due_for_purge(:limit)"),
                {"limit": BATCH_SIZE},
            )
            return [row.workspace_id for row in rows]

    async def _purge_workspace(self, workspace_id: UUID, report: PurgeReport) -> None:
        async with self._sessions() as db, workspace_tx(db, workspace_id):
            is_due = await db.scalar(
                select(Workspace.purge_after <= func.now()).where(Workspace.id == workspace_id)
            )
        if is_due:
            await self._purge_whole_workspace(workspace_id, report)
            return
        report.documents += await self._purge_deleted_documents(workspace_id, report)
        report.uploads += await self._purge_expired_uploads(workspace_id, report)
        report.exports += await self._delete_in_batches(
            workspace_id,
            lambda: delete(Export).where(
                Export.workspace_id == workspace_id,
                Export.id.in_(
                    select(Export.id)
                    .where(Export.workspace_id == workspace_id, Export.expires_at <= func.now())
                    .limit(BATCH_SIZE)
                ),
            ),
        )
        report.idempotency_keys += await self._delete_in_batches(
            workspace_id,
            lambda: delete(IdempotencyKey).where(
                IdempotencyKey.workspace_id == workspace_id,
                IdempotencyKey.key.in_(
                    select(IdempotencyKey.key)
                    .where(
                        IdempotencyKey.workspace_id == workspace_id,
                        IdempotencyKey.expires_at <= func.now(),
                    )
                    .limit(BATCH_SIZE)
                ),
            ),
        )

    async def _purge_whole_workspace(self, workspace_id: UUID, report: PurgeReport) -> None:
        """Objects first, then the row: its foreign keys cascade to every table of the workspace."""
        for bucket, prefix in (
            (self._storage.docs, f"ws/{workspace_id}/"),
            (self._storage.quarantine, f"q/{workspace_id}/"),
        ):
            # The row may go even if listing fails: its keys are already erased, ma-docs leftovers
            # are orphans for the next pass and quarantine ones expire by the lifecycle rule.
            with _storage_failure_logged("workspace_objects", report):
                batches = itertools.batched((item.key for item in bucket.list(prefix)), BATCH_SIZE)
                while keys := await asyncio.to_thread(next, batches, None):
                    await self._delete_objects(bucket, list(keys), "workspace_deleted", report)
        async with self._sessions() as db, workspace_tx(db, workspace_id):
            await db.execute(delete(Workspace).where(Workspace.id == workspace_id))
        report.workspaces += 1

    async def _purge_deleted_documents(self, workspace_id: UUID, report: PurgeReport) -> int:
        purged = 0
        while True:
            async with self._sessions() as db, workspace_tx(db, workspace_id):
                rows = (
                    await db.execute(
                        select(Document.id, DocumentFile.object_key)
                        .join(DocumentFile, DocumentFile.document_id == Document.id)
                        .where(
                            Document.workspace_id == workspace_id,
                            Document.deleted_at <= func.now() - DELETED_DOCUMENT_GRACE,
                        )
                        .limit(BATCH_SIZE)
                    )
                ).all()
            if not rows:
                return purged
            keys = [row.object_key for row in rows]
            await self._delete_objects(self._storage.docs, keys, "document_deleted", report)
            ids = [row.id for row in rows]
            async with self._sessions() as db, workspace_tx(db, workspace_id):
                await db.execute(
                    delete(Document).where(
                        Document.workspace_id == workspace_id, Document.id.in_(ids)
                    )
                )
                await db.execute(
                    _INSERT_PURGE_AUDIT,
                    [{"workspace_id": workspace_id, "entity_id": id_} for id_ in ids],
                )
            purged += len(ids)

    async def _purge_expired_uploads(self, workspace_id: UUID, report: PurgeReport) -> int:
        """Rows a day past `expires_at` and their quarantine objects, if the browser sent one."""
        purged = 0
        while True:
            async with self._sessions() as db, workspace_tx(db, workspace_id):
                rows = (
                    await db.execute(
                        select(Upload.id, Upload.quarantine_key)
                        .where(
                            Upload.workspace_id == workspace_id,
                            Upload.expires_at <= func.now() - EXPIRED_UPLOAD_GRACE,
                        )
                        .limit(BATCH_SIZE)
                    )
                ).all()
            if not rows:
                return purged
            keys = [row.quarantine_key for row in rows]
            await self._delete_objects(self._storage.quarantine, keys, "upload_expired", report)
            async with self._sessions() as db, workspace_tx(db, workspace_id):
                await db.execute(
                    delete(Upload).where(
                        Upload.workspace_id == workspace_id,
                        Upload.id.in_([row.id for row in rows]),
                    )
                )
            purged += len(rows)

    async def _delete_in_batches(self, workspace_id: UUID, statement: Callable[[], Delete]) -> int:
        purged = 0
        while True:
            async with self._sessions() as db, workspace_tx(db, workspace_id):
                result = await db.execute(statement())
            deleted: int = cast("CursorResult[Any]", result).rowcount
            purged += deleted
            if deleted < BATCH_SIZE:
                return purged

    async def _delete_objects(
        self, bucket: Bucket, keys: list[str], reason: str, report: PurgeReport
    ) -> None:
        """Delete now; whatever storage refuses goes to purge_queue for a retry."""
        failed = await asyncio.to_thread(_delete_each, bucket, keys)
        if not failed:
            return
        report.failed_deletes += len(failed)
        async with self._sessions() as db, db.begin():
            await db.execute(
                pg_insert(PurgeQueue)
                .values([{"object_key": key, "reason": reason} for key in failed])
                .on_conflict_do_nothing()
            )

    async def _drain_queue(self, report: PurgeReport) -> None:
        """purge_queue has no workspace column and no RLS: the worker reads it directly."""
        while True:
            async with self._sessions() as db, db.begin():
                rows = (
                    await db.execute(
                        select(PurgeQueue.object_key, PurgeQueue.attempts)
                        .where(PurgeQueue.next_attempt_at <= func.now())
                        .order_by(PurgeQueue.next_attempt_at)
                        .limit(BATCH_SIZE)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
                if not rows:
                    return
                for row in rows:
                    bucket = self._bucket_of(row.object_key)
                    if await asyncio.to_thread(_delete_each, bucket, [row.object_key]):
                        report.failed_deletes += 1
                        await db.execute(
                            update(PurgeQueue)
                            .where(PurgeQueue.object_key == row.object_key)
                            .values(
                                attempts=PurgeQueue.attempts + 1,
                                next_attempt_at=func.now() + retry_delay(row.attempts + 1),
                            )
                        )
                    else:
                        report.queued_objects += 1
                        await db.execute(
                            delete(PurgeQueue).where(PurgeQueue.object_key == row.object_key)
                        )
            if len(rows) < BATCH_SIZE:
                return

    def _bucket_of(self, object_key: str) -> Bucket:
        return self._storage.quarantine if object_key.startswith("q/") else self._storage.docs

    async def _purge_orphans(self, report: PurgeReport) -> None:
        """ma-docs objects older than an hour without a document_files row (05-architecture, 5.1).

        The API writes the ciphertext before its transaction, so a failed transaction leaves one.
        """
        cutoff = datetime.now(UTC) - ORPHAN_MIN_AGE
        candidates = orphan_candidates(self._storage.docs.list("ws/"), cutoff)
        while batch := await asyncio.to_thread(next, candidates, None):
            workspace_id, objects = batch
            async with self._sessions() as db, workspace_tx(db, workspace_id):
                known = set(
                    await db.scalars(
                        select(DocumentFile.document_id).where(
                            DocumentFile.workspace_id == workspace_id,
                            DocumentFile.document_id.in_(list(objects)),
                        )
                    )
                )
            orphans = [key for document_id, key in objects.items() if document_id not in known]
            await self._delete_objects(self._storage.docs, orphans, "orphan", report)
            report.orphans += len(orphans)


@contextmanager
def _storage_failure_logged(step: str, report: PurgeReport) -> Iterator[None]:
    try:
        yield
    except StorageUnavailableError:
        report.storage_failures += 1
        log.warning("purge_storage_unavailable", step=step)


def parse_object_key(key: str) -> tuple[UUID, UUID] | None:
    """`ws/{workspace}/{document}.bin` -> (workspace, document); None for anything else."""
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "ws" or not parts[2].endswith(".bin"):
        return None
    try:
        return UUID(parts[1]), UUID(parts[2].removesuffix(".bin"))
    except ValueError:
        return None


def orphan_candidates(
    objects: Iterable[StoredObject], cutoff: datetime
) -> Iterator[tuple[UUID, dict[UUID, str]]]:
    """Document objects older than `cutoff` as (workspace, {document: key}) batches of at most
    BATCH_SIZE, read lazily: a listing is sorted by key, so a workspace's objects are adjacent.
    """
    batch_workspace: UUID | None = None
    batch: dict[UUID, str] = {}
    for item in objects:
        ids = parse_object_key(item.key)
        if ids is None or item.last_modified >= cutoff:
            continue
        workspace_id, document_id = ids
        if batch_workspace is not None and (
            workspace_id != batch_workspace or len(batch) == BATCH_SIZE
        ):
            yield batch_workspace, batch
            batch = {}
        batch_workspace = workspace_id
        batch[document_id] = item.key
    if batch_workspace is not None:
        yield batch_workspace, batch


def retry_delay(attempts: int) -> timedelta:
    """1, 2, 4 ... minutes, at most six hours."""
    return min(timedelta(minutes=2 ** (attempts - 1)), MAX_RETRY_DELAY)


def _delete_each(bucket: Bucket, keys: list[str]) -> list[str]:
    """Keys that could not be deleted."""
    failed = []
    for key in keys:
        try:
            bucket.delete(key)
        except StorageUnavailableError:
            failed.append(key)
    return failed


async def main(*, once: bool) -> None:
    settings = WorkerSettings()
    configure_logging(settings.log_level)
    engine = create_engine(settings.database_url)
    storage = ObjectStorage(
        endpoint=settings.s3_endpoint,
        public_endpoint=settings.s3_endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key.get_secret_value(),
        quarantine_bucket=settings.s3_bucket_quarantine,
        docs_bucket=settings.s3_bucket_docs,
    )
    purger = Purger(create_sessionmaker(engine), storage)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    try:
        while not stop.is_set():
            try:
                report = await purger.run_once()
            # Top of the worker loop: log the type only (messages may quote SQL parameters) and
            # retry on the next tick instead of exiting; every step is idempotent.
            except Exception as exc:
                log.error("purge_failed", error_type=type(exc).__name__)
                if once:
                    raise
            else:
                log.info("purge_finished", **vars(report))
            if once:
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.purge_interval_seconds)
            except TimeoutError:
                continue
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="python -m app.workers.purge", description=__doc__.splitlines()[0]
    )
    parser.add_argument("--once", action="store_true", help="run one cleanup pass and exit")
    asyncio.run(main(once=parser.parse_args().once))
