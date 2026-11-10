"""Helpers for the uploads, documents, list, export and seed API tests (fixtures from QA-01)."""

import json
import secrets
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from httpx import AsyncClient, Response

REPO_ROOT = Path(__file__).resolve().parents[4]
MANIFEST = json.loads((REPO_ROOT / "qa/fixtures/manifest.json").read_text())
GENERATED_DIR = REPO_ROOT / "qa/fixtures/generated"


@dataclass(frozen=True)
class Source:
    path: Path
    title: str
    type: str
    document_date: str | None
    size_bytes: int
    sha256: str
    expected_order: int

    @property
    def date(self) -> date | None:
        return date.fromisoformat(self.document_date) if self.document_date else None


SOURCES = [
    Source(
        path=REPO_ROOT / item["path"],
        title=item["title"],
        type=item["type"],
        document_date=item["document_date"],
        size_bytes=item["size_bytes"],
        sha256=item["sha256"],
        expected_order=item["expected_order"],
    )
    for item in MANIFEST["sources"]
]
# TC-011: 05, 03, 04, 01, 02, 06.
EXPECTED_TITLES = [source.title for source in sorted(SOURCES, key=lambda s: s.expected_order)]


def generated(name: str) -> Path:
    """A QA-01 generated fixture; `make fixtures` (uv run qa/fixtures/generate.py) creates them."""
    path = GENERATED_DIR / name
    assert path.exists(), f"{path} is missing: run `make fixtures` first"
    return path


def write_headers(created: Response, key: str | None = None) -> dict[str, str]:
    return {
        "X-CSRF-Token": created.json()["csrf_token"],
        "Idempotency-Key": key or secrets.token_hex(16),
    }


async def request_upload(
    client: AsyncClient, created: Response, *, name: str, size_bytes: int
) -> Response:
    return await client.post(
        "/api/v1/uploads",
        headers=write_headers(created),
        json={"original_name": name, "size_bytes": size_bytes, "content_type": "application/pdf"},
    )


async def upload(client: AsyncClient, created: Response, data: bytes, name: str) -> str:
    """POST /uploads, then the browser's multipart POST straight to storage; the upload id."""
    response = await request_upload(client, created, name=name, size_bytes=len(data))
    assert response.status_code == 201, response.text
    body = response.json()
    async with httpx.AsyncClient() as browser:
        stored = await browser.post(
            body["url"], data=body["fields"], files={"file": (name, data, "application/pdf")}
        )
    assert stored.status_code == 204, stored.text
    upload_id: str = body["upload_id"]
    return upload_id


async def create_document(
    client: AsyncClient,
    created: Response,
    upload_id: str,
    *,
    key: str | None = None,
    **fields: Any,
) -> Response:
    body = {"upload_id": upload_id, "title": "Документ", "type": "other", **fields}
    return await client.post("/api/v1/documents", headers=write_headers(created, key), json=body)


async def add_source(client: AsyncClient, created: Response, source: Source) -> dict[str, Any]:
    upload_id = await upload(client, created, source.path.read_bytes(), source.path.name)
    response = await create_document(
        client,
        created,
        upload_id,
        title=source.title,
        type=source.type,
        document_date=source.document_date,
    )
    assert response.status_code == 201, response.text
    document: dict[str, Any] = response.json()
    return document


async def add_all_sources(client: AsyncClient, created: Response) -> list[dict[str, Any]]:
    """The six task fixtures in file order 01..06, as TC-011 uploads them."""
    return [await add_source(client, created, source) for source in SOURCES]
