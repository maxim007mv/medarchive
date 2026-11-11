from datetime import date
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.modules.documents.schemas import DocumentCreate, DocumentPatch

UPLOAD_ID = "01930c70-1f2a-7d3b-8c4d-5e6f7a8b9c0d"


def _create(**fields: Any) -> DocumentCreate:
    body = {"upload_id": UPLOAD_ID, "title": "Общий анализ крови", "type": "analysis", **fields}
    return DocumentCreate.model_validate(body)


def _error_types(exc_info: pytest.ExceptionInfo[ValidationError]) -> list[tuple[str, ...]]:
    return [(*map(str, error["loc"]), error["type"]) for error in exc_info.value.errors()]


def test_minimal_create_body() -> None:
    body = _create()

    assert body.upload_id == UUID(UPLOAD_ID)
    assert body.document_date is None
    assert body.note is None


def test_title_and_note_are_trimmed_and_blank_note_is_null() -> None:
    body = _create(title="  Липидограмма ", note="   ")

    assert body.title == "Липидограмма"
    assert body.note is None


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        pytest.param({"title": "   "}, ("title", "title_required"), id="TC-012-blank-title"),
        pytest.param({"title": "я" * 201}, ("title", "title_too_long"), id="title-201"),
        pytest.param({"note": "я" * 2001}, ("note", "note_too_long"), id="note-2001"),
        pytest.param(
            {"document_date": "2026-02-31"}, ("document_date", "date_invalid"), id="TC-013"
        ),
        pytest.param(
            {"document_date": "1899-12-31"}, ("document_date", "date_invalid"), id="before-1900"
        ),
        pytest.param({"document_date": 0}, ("document_date", "date_invalid"), id="unix-time"),
        pytest.param(
            {"document_date": "20260408"}, ("document_date", "date_invalid"), id="basic-format"
        ),
        pytest.param({"type": "xray"}, ("type", "type_unknown"), id="unknown-type"),
        pytest.param({"version": 2}, ("version", "extra_forbidden"), id="TC-097-extra-field"),
    ],
)
def test_create_rule_codes(fields: dict[str, Any], expected: tuple[str, str]) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _create(**fields)

    assert _error_types(exc_info) == [expected]


def test_title_of_200_chars_is_accepted() -> None:
    assert len(_create(title="я" * 200).title) == 200


def test_patch_tracks_only_sent_fields() -> None:
    patch = DocumentPatch.model_validate({"note": None, "document_date": "2026-04-08"})

    assert patch.changes() == {"note": None, "document_date": date(2026, 4, 8)}


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({}, id="empty"),
        pytest.param({"title": None}, id="null-title"),
        pytest.param({"type": None}, id="null-type"),
        pytest.param({"workspace_id": UPLOAD_ID}, id="TC-097-workspace-id"),
        pytest.param({"uploaded_at": "2026-11-10T00:00:00Z"}, id="uploaded-at-immutable"),
    ],
)
def test_patch_rejects(body: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DocumentPatch.model_validate(body)
