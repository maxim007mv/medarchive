from datetime import date
from urllib.parse import unquote

import pytest

from app.modules.documents.filenames import (
    MAX_SLUG_CHARS,
    content_disposition,
    pdf_file_name,
    slugify,
    unique_names,
)


@pytest.mark.parametrize(
    ("title", "document_date", "expected"),
    [
        (
            "УЗИ почек и мочевого пузыря",
            date(2026, 5, 22),
            "2026-05-22_uzi-pochek-i-mochevogo-puzyrya.pdf",
        ),
        ("Липидограмма", date(2026, 5, 21), "2026-05-21_lipidogramma.pdf"),
        ("Заключение терапевта", date(2026, 4, 10), "2026-04-10_zaklyuchenie-terapevta.pdf"),
        ("Общий анализ крови", date(2026, 4, 8), "2026-04-08_obshchiy-analiz-krovi.pdf"),
        (
            "Биохимический анализ крови",
            date(2026, 4, 8),
            "2026-04-08_biokhimicheskiy-analiz-krovi.pdf",
        ),
        ("ЭКГ покоя", None, "bez-daty_ekg-pokoya.pdf"),
    ],
)
def test_tc070_fixture_names_match_texts_dictionary(
    title: str, document_date: date | None, expected: str
) -> None:
    assert pdf_file_name(title, document_date) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Ёлка, щука; ЪЬ", "elka-shchuka"),
        ("MRI 2026 / v2", "mri-2026-v2"),
        ("  --Анализ--  ", "analiz"),
        ("Café", "caf"),
        ("../../etc/passwd", "etc-passwd"),
        ("«»!!!", "dokument"),
        ("", "dokument"),
    ],
)
def test_slugify_rules(title: str, expected: str) -> None:
    assert slugify(title) == expected


def test_long_slug_is_cut_at_last_dash() -> None:
    title = " ".join(["анализ"] * 30)

    slug = slugify(title)

    assert len(slug) <= MAX_SLUG_CHARS
    assert slug.endswith("analiz")
    assert slug == "-".join(["analiz"] * 11)


def test_long_single_word_is_cut_hard() -> None:
    assert slugify("a" * 200) == "a" * MAX_SLUG_CHARS


def test_duplicates_get_numeric_suffix_in_order() -> None:
    names = ["a.pdf", "b.pdf", "a.pdf", "a.pdf", "a-2.pdf"]

    assert list(unique_names(names)) == ["a.pdf", "b.pdf", "a-2.pdf", "a-3.pdf", "a-2-2.pdf"]


def test_tc024_content_disposition_has_ascii_and_utf8_names() -> None:
    header = content_disposition("attachment", "Общий анализ крови", date(2026, 4, 8))

    assert header.startswith('attachment; filename="2026-04-08_obshchiy-analiz-krovi.pdf"; ')
    utf8_part = header.split("filename*=UTF-8''", 1)[1]
    assert header.isascii()
    assert unquote(utf8_part) == "2026-04-08_Общий анализ крови.pdf"


def test_content_disposition_strips_header_breaking_characters() -> None:
    header = content_disposition("inline", 'a"b\r\nc/d', None)

    assert "\r" not in header
    assert "\n" not in header
    assert unquote(header.split("''", 1)[1]) == "bez-daty_a_b__c_d.pdf"
