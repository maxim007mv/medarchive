"""Operator commands. BE-17: load the six task fixtures through the same uploads -> documents path
as the browser, with titles, types and dates from qa/fixtures/manifest.json.

    python -m app.cli seed --new                 # new archive; prints its id and access key
    python -m app.cli seed --workspace <uuid>    # into an existing archive

The CLI opens its own short session in the archive and revokes it when done. Output carries
counts and ids only: titles stay out of logs even for synthetic fixtures (AGENTS.md).
"""

import argparse
import asyncio
import json
import secrets
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import Kek
from app.core.deps import OWNER_SCOPES, SessionContext, load_workspace_keys, session_tx
from app.core.security import new_session_token
from app.db.engine import create_engine, create_sessionmaker
from app.db.transaction import workspace_tx
from app.modules.auth import repository as auth_repository
from app.modules.auth import service as auth_service
from app.modules.auth.consent import POLICY_VERSION
from app.modules.auth.schemas import DEFAULT_TIMEZONE, WorkspaceCreate
from app.modules.documents import service as documents
from app.modules.documents.dependencies import today_in
from app.modules.documents.schemas import DocumentCreate
from app.modules.uploads import service as uploads
from app.modules.uploads.schemas import PDF_CONTENT_TYPE, UploadCreate
from app.storage.s3 import ObjectStorage

MANIFEST = Path("qa/fixtures/manifest.json")
REQUEST_ID = "cli-seed"


@dataclass(frozen=True)
class Fixture:
    path: Path
    title: str
    type: str
    document_date: date | None


class SeedError(Exception):
    pass


def load_fixtures(root: Path) -> list[Fixture]:
    """The `sources` of the manifest in file order (01..06), paths relative to `root`."""
    manifest = json.loads((root / MANIFEST).read_text())
    return [
        Fixture(
            path=root / source["path"],
            title=source["title"],
            type=source["type"],
            document_date=date.fromisoformat(source["document_date"])
            if source["document_date"]
            else None,
        )
        for source in manifest["sources"]
    ]


async def seed_workspace(
    db: AsyncSession,
    kek: Kek,
    storage: ObjectStorage,
    session: SessionContext,
    fixtures: list[Fixture],
) -> list[UUID]:
    """Upload each fixture into quarantine and create its document; returns the new ids."""
    async with session_tx(db, session):
        keys = await load_workspace_keys(db, kek, session.workspace_id)
        timezone = await auth_repository.workspace_timezone(db, session.workspace_id)
    today = today_in(timezone or DEFAULT_TIMEZONE)
    created = []
    for fixture in fixtures:
        data = fixture.path.read_bytes()
        upload = await uploads.create_upload(
            db,
            session,
            keys,
            storage,
            UploadCreate(
                original_name=fixture.path.name,
                size_bytes=len(data),
                content_type=PDF_CONTENT_TYPE,
            ),
        )
        # The browser POSTs to the presigned URL; the CLI writes the same key directly.
        with fixture.path.open("rb") as file:
            await asyncio.to_thread(storage.quarantine.upload, upload.fields["key"], file)
        document = await documents.create_document(
            db,
            session,
            keys,
            storage,
            DocumentCreate.model_validate(
                {
                    "upload_id": upload.upload_id,
                    "title": fixture.title,
                    "type": fixture.type,
                    "document_date": fixture.document_date,
                }
            ),
            today=today,
        )
        created.append(document.id)
    return created


async def _new_workspace(db: AsyncSession, kek: Kek) -> tuple[SessionContext, str]:
    created = await auth_service.create_workspace(
        db,
        kek,
        key=secrets.token_hex(16),
        payload=WorkspaceCreate.model_validate(
            {"consent": {"policy_version": POLICY_VERSION, "accepted": True}}
        ),
        meta=auth_service.RequestMeta(REQUEST_ID, None),
    )
    access_key: str = created.body["access_key"]
    return _context(created.session.workspace_id, created.session.session_id), access_key


async def _session_in(db: AsyncSession, workspace_id: UUID) -> SessionContext:
    _, token_sha256 = new_session_token()
    async with workspace_tx(db, workspace_id, request_id=REQUEST_ID):
        session = await auth_repository.create_session(db, token_sha256)
    if session is None:
        raise SeedError(f"workspace {workspace_id} does not exist or is deleted")
    return _context(workspace_id, session.session_id)


def _context(workspace_id: UUID, session_id: UUID) -> SessionContext:
    return SessionContext(
        session_id=session_id,
        workspace_id=workspace_id,
        scopes=OWNER_SCOPES,
        request_id=REQUEST_ID,
    )


async def seed(*, workspace_id: UUID | None, root: Path) -> None:
    settings = get_settings()
    kek = Kek.from_file(settings.kek_keyset_path)
    storage = ObjectStorage.from_settings(settings)
    fixtures = load_fixtures(root)
    engine = create_engine(settings.database_url)
    try:
        async with create_sessionmaker(engine)() as db:
            access_key = None
            if workspace_id is None:
                session, access_key = await _new_workspace(db, kek)
            else:
                session = await _session_in(db, workspace_id)
            try:
                created = await seed_workspace(db, kek, storage, session, fixtures)
            finally:
                async with session_tx(db, session):
                    await auth_repository.revoke_session(db, session.session_id)
    finally:
        await engine.dispose()
    print(f"workspace: {session.workspace_id}")
    print(f"documents created: {len(created)}")
    if access_key:
        print(f"access key: {access_key}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    seed_parser = commands.add_parser("seed", help="load the six fixtures (BE-17)")
    target = seed_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--workspace", type=UUID, help="id of an existing archive")
    target.add_argument("--new", action="store_true", help="create a new archive first")
    seed_parser.add_argument(
        "--root",
        type=Path,
        help="directory with qa/fixtures/manifest.json and the PDFs it lists"
        " (default: the checkout of apps/api; the image has no repository, make seed mounts one)",
    )
    args = parser.parse_args()
    root = args.root or Path(__file__).resolve().parents[3]
    try:
        asyncio.run(seed(workspace_id=args.workspace, root=root))
    except SeedError as exc:
        parser.exit(1, f"seed failed: {exc}\n")


if __name__ == "__main__":
    main()
