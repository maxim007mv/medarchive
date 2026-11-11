"""documents and document_files. Call inside `workspace_tx`; every query filters by workspace_id
as well, which gives the planner the literal for the composite indexes (07-database, section 7).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ColumnElement,
    Select,
    and_,
    case,
    cast,
    false,
    func,
    insert,
    literal,
    or_,
    select,
    text,
    true,
    tuple_,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Consent, Document, DocumentFile, DocumentType
from app.modules.documents.listing import (
    UNDATED_LIST_KEY,
    ListFilter,
    OrderBy,
    Position,
    list_key,
)
from app.modules.documents.schemas import TypeCode

_SOFT_DELETE = text("SELECT app.soft_delete_document(:document_id)")


@dataclass(frozen=True)
class StoredDocument:
    id: UUID
    type_code: TypeCode
    title_ct: bytes
    note_ct: bytes | None
    document_date: date | None
    uploaded_at: datetime
    updated_at: datetime
    version: int
    object_key: str
    size_bytes: int
    sha256: bytes
    page_count: int | None
    original_name_ct: bytes


@dataclass(frozen=True)
class ListedDocument:
    id: UUID
    type_code: TypeCode
    title_ct: bytes
    document_date: date | None
    uploaded_at: datetime
    has_note: bool
    size_bytes: int
    version: int
    in_date_range: bool


@dataclass(frozen=True)
class ListCounts:
    total: int
    matched: int
    undated_excluded: int


@dataclass(frozen=True)
class NewDocument:
    id: UUID
    type_code: TypeCode
    title_ct: bytes
    title_bidx: list[int]
    note_ct: bytes | None
    document_date: date | None
    object_key: str
    size_bytes: int
    sha256: bytes
    page_count: int | None
    original_name_ct: bytes


def object_key(workspace_id: UUID, document_id: UUID) -> str:
    return f"ws/{workspace_id}/{document_id}.bin"


async def has_active_consent(db: AsyncSession, workspace_id: UUID) -> bool:
    consent_id = await db.scalar(
        select(Consent.id).where(
            Consent.workspace_id == workspace_id, Consent.withdrawn_at.is_(None)
        )
    )
    return consent_id is not None


async def insert_document(
    db: AsyncSession, workspace_id: UUID, document: NewDocument
) -> tuple[datetime, datetime, int]:
    """Insert the document and its file; returns the DB-set (uploaded_at, updated_at, version)."""
    row = (
        await db.execute(
            insert(Document)
            .values(
                id=document.id,
                workspace_id=workspace_id,
                type_code=document.type_code,
                title_ct=document.title_ct,
                title_bidx=document.title_bidx,
                note_ct=document.note_ct,
                document_date=document.document_date,
            )
            .returning(Document.uploaded_at, Document.updated_at, Document.version)
        )
    ).one()
    await db.execute(
        insert(DocumentFile).values(
            document_id=document.id,
            workspace_id=workspace_id,
            object_key=document.object_key,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            page_count=document.page_count,
            original_name_ct=document.original_name_ct,
        )
    )
    return row.uploaded_at, row.updated_at, row.version


def _stored_columns() -> Select[*tuple[Any, ...]]:
    return select(
        Document.id,
        Document.type_code,
        Document.title_ct,
        Document.note_ct,
        Document.document_date,
        Document.uploaded_at,
        Document.updated_at,
        Document.version,
        DocumentFile.object_key,
        DocumentFile.size_bytes,
        DocumentFile.sha256,
        DocumentFile.page_count,
        DocumentFile.original_name_ct,
    ).join(DocumentFile, DocumentFile.document_id == Document.id)


async def get_document(
    db: AsyncSession, workspace_id: UUID, document_id: UUID, *, for_update: bool = False
) -> StoredDocument | None:
    """A visible (not deleted) document; `for_update` locks it until the transaction ends."""
    query = _stored_columns().where(*_visible(workspace_id), Document.id == document_id)
    if for_update:
        query = query.with_for_update(of=Document)
    row = (await db.execute(query)).one_or_none()
    return None if row is None else StoredDocument(**row._asdict())


async def get_documents(
    db: AsyncSession, workspace_id: UUID, document_ids: list[UUID]
) -> list[StoredDocument]:
    """Visible documents among `document_ids`, in no particular order."""
    query = _stored_columns().where(*_visible(workspace_id), Document.id.in_(document_ids))
    return [StoredDocument(**row._asdict()) for row in await db.execute(query)]


async def update_document(
    db: AsyncSession, workspace_id: UUID, document_id: UUID, values: dict[str, Any]
) -> tuple[datetime, int]:
    """Returns (updated_at, version) after the bump_version trigger."""
    row = (
        await db.execute(
            update(Document)
            .where(Document.workspace_id == workspace_id, Document.id == document_id)
            .values(**values)
            .returning(Document.updated_at, Document.version)
        )
    ).one()
    return row.updated_at, row.version


async def soft_delete(db: AsyncSession, workspace_id: UUID, document_id: UUID) -> bool:
    """`deleted_at = now()` through `app.soft_delete_document`: hide_deleted forbids a plain
    UPDATE. The function scopes to `app.current_workspace()`, which is `workspace_id` here.
    """
    deleted: bool = (await db.execute(_SOFT_DELETE, {"document_id": document_id})).scalar_one()
    return deleted


async def type_titles(db: AsyncSession) -> dict[str, str]:
    """The document_types lookup (not workspace data, no RLS)."""
    rows = await db.execute(select(DocumentType.code, DocumentType.title_ru))
    return {row.code: row.title_ru for row in rows}


def _date_condition(list_filter: ListFilter, tz: str) -> ColumnElement[bool]:
    # Document dates are compared through list_key, the leading column of documents_list after
    # workspace_id, so a period is an index range (Q3, Q6) rather than a filter over the archive.
    if list_filter.undated:
        return Document.list_key == UNDATED_LIST_KEY
    conditions: list[ColumnElement[bool]] = []
    if list_filter.date_field == "document":
        # list_key falls as the date grows, and undated rows hold the largest key.
        if list_filter.date_to:
            conditions.append(Document.list_key >= list_key(list_filter.date_to))
        if list_filter.date_from:
            conditions.append(Document.list_key <= list_key(list_filter.date_from))
        elif list_filter.date_to:
            conditions.append(Document.list_key < UNDATED_LIST_KEY)
    else:
        # Day boundaries of the user's zone, as `timestamp AT TIME ZONE tz`; the column itself is
        # not wrapped in a function, so documents_by_upload stays usable (Q5).
        if list_filter.date_from:
            conditions.append(Document.uploaded_at >= _midnight(list_filter.date_from, tz))
        if list_filter.date_to:
            conditions.append(
                Document.uploaded_at < _midnight(list_filter.date_to + timedelta(days=1), tz)
            )
    return and_(true(), *conditions)


def _midnight(day: date, tz: str) -> ColumnElement[datetime]:
    return func.timezone(tz, cast(literal(day), TIMESTAMP))


def _visible(workspace_id: UUID) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    return Document.workspace_id == workspace_id, Document.deleted_at.is_(None)


def _type_condition(list_filter: ListFilter) -> ColumnElement[bool]:
    return Document.type_code.in_(list_filter.types) if list_filter.types else true()


def _listed_columns(in_date_range: ColumnElement[bool]) -> Select[*tuple[Any, ...]]:
    return select(
        Document.id,
        Document.type_code,
        Document.title_ct,
        Document.document_date,
        Document.uploaded_at,
        Document.note_ct.is_not(None).label("has_note"),
        DocumentFile.size_bytes,
        Document.version,
        in_date_range.label("in_date_range"),
    ).join(DocumentFile, DocumentFile.document_id == Document.id)


def _undated_flag() -> ColumnElement[int]:
    return case((Document.document_date.is_(None), 1), else_=0)


def _order(order_by: OrderBy) -> tuple[ColumnElement[Any], ...]:
    if order_by == "document_date desc":
        return Document.list_key.asc(), Document.uploaded_at.asc(), Document.id.asc()
    return _undated_flag(), Document.uploaded_at.desc(), Document.id.desc()


def _after(order_by: OrderBy, position: Position) -> ColumnElement[bool]:
    if order_by == "document_date desc":
        return tuple_(Document.list_key, Document.uploaded_at, Document.id) > tuple_(
            position.group, position.uploaded_at, position.id
        )
    undated = _undated_flag()
    return or_(
        undated > position.group,
        and_(
            undated == position.group,
            tuple_(Document.uploaded_at, Document.id) < tuple_(position.uploaded_at, position.id),
        ),
    )


async def count_documents(
    db: AsyncSession, workspace_id: UUID, list_filter: ListFilter, tz: str
) -> ListCounts:
    """total, matched and undated_excluded in one pass (Q3) for a filter without search."""
    by_type = _type_condition(list_filter)
    excluded = (
        and_(by_type, Document.document_date.is_(None))
        if list_filter.excludes_undated_by_date
        else false()
    )
    row = (
        await db.execute(
            select(
                func.count().label("total"),
                func.count()
                .filter(and_(by_type, _date_condition(list_filter, tz)))
                .label("matched"),
                func.count().filter(excluded).label("undated_excluded"),
            ).where(*_visible(workspace_id))
        )
    ).one()
    return ListCounts(row.total, row.matched, row.undated_excluded)


async def list_matching(
    db: AsyncSession,
    workspace_id: UUID,
    list_filter: ListFilter,
    tz: str,
    order_by: OrderBy,
    *,
    after: Position | None = None,
    limit: int | None = None,
) -> list[ListedDocument]:
    """Documents of a filter without search, in list order, keyset-paginated."""
    query = _listed_columns(true()).where(
        *_visible(workspace_id), _type_condition(list_filter), _date_condition(list_filter, tz)
    )
    if after is not None:
        query = query.where(_after(order_by, after))
    query = query.order_by(*_order(order_by)).limit(limit)
    return [ListedDocument(**row._asdict()) for row in await db.execute(query)]


async def search_candidates(
    db: AsyncSession, workspace_id: UUID, list_filter: ListFilter, tz: str, bidx: list[int]
) -> list[ListedDocument]:
    """Blind index hits ignoring the date filter, flagged with `in_date_range` (ADR-046).

    The caller confirms each hit on the decrypted title, then counts and pages in memory.
    """
    query = _listed_columns(_date_condition(list_filter, tz)).where(
        *_visible(workspace_id), _type_condition(list_filter), Document.title_bidx.contains(bidx)
    )
    return [ListedDocument(**row._asdict()) for row in await db.execute(query)]


async def count_all(db: AsyncSession, workspace_id: UUID) -> int:
    total: int = (
        await db.execute(select(func.count()).where(*_visible(workspace_id)))
    ).scalar_one()
    return total


async def get_listed(
    db: AsyncSession, workspace_id: UUID, document_ids: list[UUID]
) -> list[ListedDocument]:
    """Visible documents among `document_ids`, in the default list order."""
    query = (
        _listed_columns(true())
        .where(*_visible(workspace_id), Document.id.in_(document_ids))
        .order_by(*_order("document_date desc"))
    )
    return [ListedDocument(**row._asdict()) for row in await db.execute(query)]
