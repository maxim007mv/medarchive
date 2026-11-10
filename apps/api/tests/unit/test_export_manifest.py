import csv
import io
import json
from datetime import UTC, date, datetime, timedelta, timezone

from app.modules.exports.manifest import CSV_COLUMNS, ManifestEntry, build_csv, build_json

MSK = timezone(timedelta(hours=3))
ENTRIES = [
    ManifestEntry(
        title="Общий анализ крови",
        type_code="analysis",
        type_title="Анализ",
        document_date=date(2026, 4, 8),
        uploaded_at=datetime(2026, 11, 10, 19, 2, 11, 123456, tzinfo=MSK),
        note='Холестерин; "выше" нормы\nпересдать',
        file_name="2026-04-08_obshchiy-analiz-krovi.pdf",
        size_bytes=79114,
        sha256=bytes.fromhex("7ad726f5a3663e693c376562e03a2e9cc13c800112e92c09ff4f3f959560cc93"),
    ),
    ManifestEntry(
        title="=HYPERLINK(1)",
        type_code="conclusion",
        type_title="Заключение",
        document_date=None,
        uploaded_at=datetime(2026, 11, 10, 16, 5, tzinfo=UTC),
        note=None,
        file_name="bez-daty_hyperlink-1.pdf",
        size_bytes=1,
        sha256=bytes(32),
    ),
]


def _csv_rows(data: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig")), delimiter=";"))


def test_tc070_csv_has_bom_semicolons_and_columns() -> None:
    data = build_csv(ENTRIES)

    assert data.startswith(b"\xef\xbb\xbf")
    rows = _csv_rows(data)
    assert tuple(rows[0]) == CSV_COLUMNS
    assert rows[1] == [
        "Общий анализ крови",
        "Анализ",
        "2026-04-08",
        "2026-11-10T16:02:11Z",
        'Холестерин; "выше" нормы\nпересдать',
        "2026-04-08_obshchiy-analiz-krovi.pdf",
        "79114",
        "7ad726f5a3663e693c376562e03a2e9cc13c800112e92c09ff4f3f959560cc93",
    ]


def test_csv_undated_row_and_formula_neutralized() -> None:
    row = _csv_rows(build_csv(ENTRIES))[2]

    assert row[0] == "'=HYPERLINK(1)"
    assert row[2] == ""
    assert row[4] == ""


def test_json_mirrors_csv_with_type_code() -> None:
    rows = json.loads(build_json(ENTRIES))

    assert rows[0] == {
        "title": "Общий анализ крови",
        "type": "analysis",
        "document_date": "2026-04-08",
        "uploaded_at": "2026-11-10T16:02:11Z",
        "note": 'Холестерин; "выше" нормы\nпересдать',
        "file_name": "2026-04-08_obshchiy-analiz-krovi.pdf",
        "size_bytes": 79114,
        "sha256": "7ad726f5a3663e693c376562e03a2e9cc13c800112e92c09ff4f3f959560cc93",
    }
    assert rows[1]["title"] == "=HYPERLINK(1)"
    assert rows[1]["document_date"] is None
    assert rows[1]["note"] is None
