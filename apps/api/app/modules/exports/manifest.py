"""documents.csv and documents.json inside the export ZIP (docs/texts.md, section 13)."""

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

CSV_COLUMNS = (
    "title",
    "type",
    "document_date",
    "uploaded_at",
    "note",
    "file_name",
    "size_bytes",
    "sha256",
)
# Excel opens UTF-8 CSV with Cyrillic correctly only with a byte order mark.
UTF8_BOM = "\ufeff"
# OWASP CSV injection: a cell starting with one of these is a formula in Excel.
FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class ManifestEntry:
    title: str
    type_code: str
    type_title: str
    document_date: date | None
    uploaded_at: datetime
    note: str | None
    file_name: str
    size_bytes: int
    sha256: bytes


def build_csv(entries: list[ManifestEntry]) -> bytes:
    """Semicolon-separated table for Excel; the type column holds the Russian type name."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(CSV_COLUMNS)
    for entry in entries:
        writer.writerow(
            (
                _neutralize_formula(entry.title),
                entry.type_title,
                entry.document_date.isoformat() if entry.document_date else "",
                _utc_timestamp(entry.uploaded_at),
                _neutralize_formula(entry.note or ""),
                entry.file_name,
                entry.size_bytes,
                entry.sha256.hex(),
            )
        )
    return (UTF8_BOM + out.getvalue()).encode()


def build_json(entries: list[ManifestEntry]) -> bytes:
    """The same rows as the CSV, with the type code as in the API."""
    rows = [
        {
            "title": entry.title,
            "type": entry.type_code,
            "document_date": entry.document_date.isoformat() if entry.document_date else None,
            "uploaded_at": _utc_timestamp(entry.uploaded_at),
            "note": entry.note,
            "file_name": entry.file_name,
            "size_bytes": entry.size_bytes,
            "sha256": entry.sha256.hex(),
        }
        for entry in entries
    ]
    return json.dumps(rows, ensure_ascii=False, indent=2).encode()


def _neutralize_formula(value: str) -> str:
    return f"'{value}" if value.startswith(FORMULA_TRIGGERS) else value


def _utc_timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
