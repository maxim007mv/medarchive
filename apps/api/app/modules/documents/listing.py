"""List parameters, sort order and cursors (06-api-contract, section 4; TZ-backend, section 3).

Both orders put undated documents last and are keyset-paginated by a `Position`:
- `document_date desc`: ascending (list_key, uploaded_at, id), list_key is the generated column;
- `uploaded_at desc`: ascending undated flag, then (uploaded_at, id) descending.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.errors import ErrorCode, FieldError, ProblemError
from app.core.page_token import CursorValue, list_fingerprint

OrderBy = Literal["document_date desc", "uploaded_at desc"]
DateField = Literal["document", "uploaded"]
DEFAULT_ORDER: OrderBy = "document_date desc"
# documents.list_key of a NULL document_date (07-data-model.sql).
UNDATED_LIST_KEY = 2147483647
LIST_KEY_EPOCH = date(1900, 1, 1)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND = timedelta(microseconds=1)


@dataclass(frozen=True)
class ListFilter:
    """Validated filter; `query` is None when there is no search."""

    query: str | None = None
    types: tuple[str, ...] = ()
    date_field: DateField = "document"
    date_from: date | None = None
    date_to: date | None = None
    undated: bool = False

    @property
    def has_date_range(self) -> bool:
        return self.date_from is not None or self.date_to is not None

    @property
    def excludes_undated_by_date(self) -> bool:
        """Undated documents drop out only because of a document date range."""
        return self.date_field == "document" and self.has_date_range


def build_filter(
    *,
    q: str | None,
    types: list[str] | None,
    date_field: DateField,
    date_from: date | None,
    date_to: date | None,
    undated: bool,
) -> ListFilter:
    """Apply the contract rules; the schema has already rejected 1-2 character queries."""
    query = (q or "").strip() or None
    unique_types = tuple(sorted(set(types or ())))
    if undated:
        return ListFilter(query=query, types=unique_types, undated=True)
    if date_from and date_to and date_from > date_to:
        raise ProblemError(
            ErrorCode.DATE_RANGE_INVALID,
            errors=[FieldError("/from", ErrorCode.DATE_RANGE_INVALID)],
        )
    return ListFilter(query, unique_types, date_field, date_from, date_to)


def parse_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ProblemError(ErrorCode.VALIDATION_ERROR, errors=[FieldError("/tz")]) from None


def fingerprint(list_filter: ListFilter, tz: str, order_by: OrderBy) -> bytes:
    return list_fingerprint({**asdict(list_filter), "tz": tz, "order_by": order_by})


def list_key(document_date: date | None) -> int:
    """Same value as the generated column `documents.list_key`."""
    return UNDATED_LIST_KEY if document_date is None else (LIST_KEY_EPOCH - document_date).days


@dataclass(frozen=True)
class Position:
    """Sort values of one row; a page token stores the position of the last row of a page."""

    group: int  # list_key for `document_date desc`, 1 for undated else 0 for `uploaded_at desc`
    uploaded_at: datetime
    id: UUID

    @classmethod
    def of(
        cls, order_by: OrderBy, document_date: date | None, uploaded_at: datetime, id: UUID
    ) -> "Position":
        if order_by == "document_date desc":
            return cls(list_key(document_date), uploaded_at, id)
        return cls(int(document_date is None), uploaded_at, id)

    def sort_key(self, order_by: OrderBy) -> tuple[int, int, int]:
        micros = (self.uploaded_at - _EPOCH) // _MICROSECOND
        if order_by == "document_date desc":
            return self.group, micros, self.id.int
        return self.group, -micros, -self.id.int

    def to_cursor(self) -> dict[str, CursorValue]:
        return {"g": self.group, "u": self.uploaded_at.isoformat(), "i": str(self.id)}

    @classmethod
    def from_cursor(cls, cursor: dict[str, CursorValue]) -> "Position":
        try:
            uploaded_at = datetime.fromisoformat(str(cursor["u"]))
            position = cls(int(cursor["g"]), uploaded_at, UUID(str(cursor["i"])))
        except (KeyError, ValueError, TypeError):
            raise ProblemError(ErrorCode.INVALID_PAGE_TOKEN) from None
        if uploaded_at.tzinfo is None:
            raise ProblemError(ErrorCode.INVALID_PAGE_TOKEN)
        return position

