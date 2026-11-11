"""Read side of documents for the list and for exports (BE-07, BE-11).

Without `q` the database counts and pages (keyset). With `q` the blind index only yields
candidates: titles are decrypted, the substring confirmed, then counted and paged in memory by
the same sort keys as the SQL keyset (ADR-046).
"""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import blind_index
from app.core.crypto import WorkspaceKeys
from app.core.deps import SessionContext, session_tx
from app.core.page_token import PageTokenCodec
from app.modules.documents import repository
from app.modules.documents.listing import ListFilter, OrderBy, Position, fingerprint
from app.modules.documents.repository import ListCounts, ListedDocument
from app.modules.documents.schemas import DocumentList, DocumentListItem


async def list_documents(
    db: AsyncSession,
    session: SessionContext,
    keys: WorkspaceKeys,
    codec: PageTokenCodec,
    *,
    list_filter: ListFilter,
    tz: str,
    order_by: OrderBy,
    page_size: int,
    page_token: str | None,
) -> DocumentList:
    list_fingerprint = fingerprint(list_filter, tz, order_by)
    after = Position.from_cursor(codec.decode(page_token, list_fingerprint)) if page_token else None
    workspace_id = session.workspace_id
    async with session_tx(db, session):
        if list_filter.query is None:
            counts = await repository.count_documents(db, workspace_id, list_filter, tz)
            rows = await repository.list_matching(
                db, workspace_id, list_filter, tz, order_by, after=after, limit=page_size + 1
            )
        else:
            total = await repository.count_all(db, workspace_id)
            candidates = await repository.search_candidates(
                db, workspace_id, list_filter, tz, keys.query_bidx(list_filter.query)
            )
    # Tink AEAD is sync and CPU-bound: keep it off the event loop so 50 VU of list+search
    # still share the loop with DB I/O (k6 p95 budget, DoD 4).
    if list_filter.query is None:
        titles = await asyncio.to_thread(_decrypt_titles, keys, rows)
    else:
        titles, rows, counts = await asyncio.to_thread(
            _confirm_search, keys, candidates, list_filter, total, order_by, after
        )
        rows = rows[: page_size + 1]
    page = rows[:page_size]
    next_page_token = ""
    if len(rows) > page_size:
        last = page[-1]
        position = Position.of(order_by, last.document_date, last.uploaded_at, last.id)
        next_page_token = codec.encode(position.to_cursor(), list_fingerprint)
    return DocumentList(
        items=[_to_list_item(row, titles[row.id]) for row in page],
        total=counts.total,
        matched=counts.matched,
        undated_excluded=counts.undated_excluded,
        next_page_token=next_page_token,
    )


async def find_matching(
    db: AsyncSession,
    session: SessionContext,
    keys: WorkspaceKeys,
    *,
    list_filter: ListFilter,
    tz: str,
) -> list[ListedDocument]:
    """Every document of a filter in the default order (export scope `filtered`)."""
    order_by: OrderBy = "document_date desc"
    async with session_tx(db, session):
        if list_filter.query is None:
            return await repository.list_matching(
                db, session.workspace_id, list_filter, tz, order_by
            )
        candidates = await repository.search_candidates(
            db, session.workspace_id, list_filter, tz, keys.query_bidx(list_filter.query)
        )
    _, rows, _ = await asyncio.to_thread(
        _confirm_search, keys, candidates, list_filter, 0, order_by, None
    )
    return rows


def _confirm_search(
    keys: WorkspaceKeys,
    candidates: list[ListedDocument],
    list_filter: ListFilter,
    total: int,
    order_by: OrderBy,
    after: Position | None,
) -> tuple[dict[UUID, str], list[ListedDocument], ListCounts]:
    """Decrypt, confirm, count and order in one thread (ADR-046)."""
    titles = _decrypt_titles(keys, candidates)
    rows, counts = _search_results(candidates, titles, list_filter, total, order_by, after)
    return titles, rows, counts


def _search_results(
    candidates: list[ListedDocument],
    titles: dict[UUID, str],
    list_filter: ListFilter,
    total: int,
    order_by: OrderBy,
    after: Position | None,
) -> tuple[list[ListedDocument], ListCounts]:
    """Confirm blind index hits on the decrypted titles, then count and order them (ADR-046)."""
    query = list_filter.query or ""
    confirmed = [row for row in candidates if blind_index.contains_query(titles[row.id], query)]
    matched = [row for row in confirmed if row.in_date_range]
    undated_excluded = (
        sum(row.document_date is None for row in confirmed)
        if list_filter.excludes_undated_by_date
        else 0
    )

    def sort_key(row: ListedDocument) -> tuple[int, int, int]:
        return Position.of(order_by, row.document_date, row.uploaded_at, row.id).sort_key(order_by)

    ordered = sorted(matched, key=sort_key)
    if after is not None:
        after_key = after.sort_key(order_by)
        ordered = [row for row in ordered if sort_key(row) > after_key]
    return ordered, ListCounts(total, len(matched), undated_excluded)


def _decrypt_titles(keys: WorkspaceKeys, rows: list[ListedDocument]) -> dict[UUID, str]:
    return {row.id: keys.decrypt_field(row.title_ct, row.id.bytes) for row in rows}


def _to_list_item(row: ListedDocument, title: str) -> DocumentListItem:
    return DocumentListItem(
        id=row.id,
        title=title,
        type=row.type_code,
        document_date=row.document_date,
        uploaded_at=row.uploaded_at,
        has_note=row.has_note,
        size_bytes=row.size_bytes,
        version=row.version,
    )


async def get_selected(
    db: AsyncSession, session: SessionContext, document_ids: list[UUID]
) -> list[ListedDocument]:
    """Visible documents among `document_ids` in the default order (export scope `selected`)."""
    async with session_tx(db, session):
        return await repository.get_listed(db, session.workspace_id, document_ids)


@dataclass(frozen=True)
class ExportItem:
    """A decrypted document with what the ZIP needs to name and stream it."""

    id: UUID
    title: str
    type_code: str
    type_title: str
    document_date: date | None
    uploaded_at: datetime
    note: str | None
    object_key: str
    size_bytes: int
    sha256: bytes


async def get_export_items(
    db: AsyncSession, session: SessionContext, keys: WorkspaceKeys, document_ids: list[UUID]
) -> list[ExportItem]:
    """Still visible documents in the order of `document_ids` (deleted ones drop out)."""
    async with session_tx(db, session):
        stored = await repository.get_documents(db, session.workspace_id, document_ids)
        type_titles = await repository.type_titles(db)
    by_id = {document.id: document for document in stored}
    items = []
    for document_id in document_ids:
        document = by_id.get(document_id)
        if document is None:
            continue
        aad = document.id.bytes
        items.append(
            ExportItem(
                id=document.id,
                title=keys.decrypt_field(document.title_ct, aad),
                type_code=document.type_code,
                type_title=type_titles[document.type_code],
                document_date=document.document_date,
                uploaded_at=document.uploaded_at,
                note=keys.decrypt_field(document.note_ct, aad) if document.note_ct else None,
                object_key=document.object_key,
                size_bytes=document.size_bytes,
                sha256=document.sha256,
            )
        )
    return items
