from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from app.core.errors import ErrorCode, ProblemError
from app.modules.documents.listing import (
    UNDATED_LIST_KEY,
    DateField,
    ListFilter,
    OrderBy,
    Position,
    build_filter,
    fingerprint,
    list_key,
    parse_timezone,
)

UPLOADED = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


def _filter(
    *,
    q: str | None = None,
    types: list[str] | None = None,
    date_field: DateField = "document",
    date_from: date | None = None,
    date_to: date | None = None,
    undated: bool = False,
) -> ListFilter:
    return build_filter(
        q=q,
        types=types,
        date_field=date_field,
        date_from=date_from,
        date_to=date_to,
        undated=undated,
    )


@pytest.mark.parametrize(("q", "expected"), [(None, None), ("", None), ("   ", None)])
def test_blank_query_means_no_search(q: str | None, expected: None) -> None:
    assert _filter(q=q).query is expected


def test_query_is_trimmed() -> None:
    assert _filter(q="  анализ ").query == "анализ"


def test_types_are_unique_and_sorted() -> None:
    assert _filter(types=["other", "analysis", "other"]).types == ("analysis", "other")


def test_tc039_from_after_to_is_rejected() -> None:
    with pytest.raises(ProblemError) as exc_info:
        _filter(date_from=date(2026, 4, 30), date_to=date(2026, 4, 1))

    assert exc_info.value.code is ErrorCode.DATE_RANGE_INVALID
    assert [error.pointer for error in exc_info.value.errors] == ["/from"]


@pytest.mark.parametrize(
    ("date_from", "date_to"),
    [(date(2026, 4, 1), None), (None, date(2026, 4, 30)), (date(2026, 4, 8), date(2026, 4, 8))],
)
def test_open_and_single_day_ranges_are_valid(date_from: date | None, date_to: date | None) -> None:
    assert _filter(date_from=date_from, date_to=date_to).has_date_range


def test_undated_ignores_date_parameters_even_if_inverted() -> None:
    list_filter = _filter(
        undated=True,
        date_field="uploaded",
        date_from=date(2026, 4, 30),
        date_to=date(2026, 4, 1),
    )

    assert list_filter == ListFilter(undated=True)
    assert not list_filter.excludes_undated_by_date


def test_only_document_date_range_excludes_undated() -> None:
    assert _filter(date_from=date(2026, 4, 1)).excludes_undated_by_date
    assert not _filter(date_field="uploaded", date_from=date(2026, 4, 1)).excludes_undated_by_date
    assert not _filter().excludes_undated_by_date


def test_invalid_timezone_is_validation_error() -> None:
    with pytest.raises(ProblemError) as exc_info:
        parse_timezone("Mars/Olympus")

    assert exc_info.value.code is ErrorCode.VALIDATION_ERROR
    assert parse_timezone("Europe/Moscow").key == "Europe/Moscow"


def test_tc043_fingerprint_changes_with_every_parameter() -> None:
    base = fingerprint(_filter(), "Europe/Moscow", "document_date desc")

    variants = [
        fingerprint(_filter(q="анализ"), "Europe/Moscow", "document_date desc"),
        fingerprint(_filter(types=["analysis"]), "Europe/Moscow", "document_date desc"),
        fingerprint(_filter(date_from=date(2026, 4, 1)), "Europe/Moscow", "document_date desc"),
        fingerprint(_filter(date_to=date(2026, 4, 1)), "Europe/Moscow", "document_date desc"),
        fingerprint(_filter(date_field="uploaded"), "Europe/Moscow", "document_date desc"),
        fingerprint(_filter(undated=True), "Europe/Moscow", "document_date desc"),
        fingerprint(_filter(), "UTC", "document_date desc"),
        fingerprint(_filter(), "Europe/Moscow", "uploaded_at desc"),
    ]

    assert base not in variants
    assert len(set(variants)) == len(variants)
    assert fingerprint(_filter(), "Europe/Moscow", "document_date desc") == base


def test_list_key_matches_generated_column() -> None:
    assert list_key(date(1900, 1, 1)) == 0
    assert list_key(date(2026, 5, 22)) < list_key(date(2026, 4, 8))
    assert list_key(None) == UNDATED_LIST_KEY


def _sorted_titles(order_by: OrderBy) -> list[str]:
    rows = [
        ("01", date(2026, 4, 8), 0),
        ("02", date(2026, 4, 8), 1),
        ("03", date(2026, 5, 21), 2),
        ("04", date(2026, 4, 10), 3),
        ("05", date(2026, 5, 22), 4),
        ("06", None, 5),
    ]
    positions = {
        title: Position.of(
            order_by, document_date, UPLOADED + timedelta(minutes=minute), UUID(int=minute + 1)
        )
        for title, document_date, minute in rows
    }
    return sorted(positions, key=lambda title: positions[title].sort_key(order_by))


def test_tc011_default_order_by_document_date_then_upload_order() -> None:
    assert _sorted_titles("document_date desc") == ["05", "03", "04", "01", "02", "06"]


def test_tc010_uploaded_order_newest_first_with_undated_last() -> None:
    assert _sorted_titles("uploaded_at desc") == ["05", "04", "03", "02", "01", "06"]


def test_position_roundtrips_through_cursor() -> None:
    position = Position.of("uploaded_at desc", None, UPLOADED, UUID(int=7))

    assert Position.from_cursor(position.to_cursor()) == position


@pytest.mark.parametrize(
    "cursor",
    [{}, {"g": 1, "u": "not a date", "i": str(UUID(int=1))}, {"g": 1, "u": "2026-11-10T09:00:00"}],
)
def test_malformed_cursor_is_invalid_page_token(cursor: dict[str, str | int]) -> None:
    with pytest.raises(ProblemError) as exc_info:
        Position.from_cursor(cursor)

    assert exc_info.value.code is ErrorCode.INVALID_PAGE_TOKEN
