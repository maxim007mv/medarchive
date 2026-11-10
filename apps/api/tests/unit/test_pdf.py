from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from app.modules.uploads.pdf import PdfRejectedError, inspect_pdf

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_PDF = REPO_ROOT / "MedArchive/05_qa/fixtures/01-general-blood-test.pdf"
OWNER = "owner"
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def _pdf_with_pages(page_count: int) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=595, height=842)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _encrypted(source: bytes, user_password: str) -> bytes:
    writer = PdfWriter(clone_from=PdfReader(BytesIO(source)))
    writer.encrypt(user_password=user_password, owner_password=OWNER, algorithm="AES-256")
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _reject_code(data: bytes) -> str:
    with pytest.raises(PdfRejectedError) as exc_info:
        inspect_pdf(BytesIO(data))
    return exc_info.value.code


def test_source_fixture_has_one_page() -> None:
    assert inspect_pdf(BytesIO(SOURCE_PDF.read_bytes())) == 1


def test_counts_pages() -> None:
    assert inspect_pdf(BytesIO(_pdf_with_pages(3))) == 3


def test_page_count_above_schema_limit_is_not_stored() -> None:
    assert inspect_pdf(BytesIO(_pdf_with_pages(2001))) is None


@pytest.mark.parametrize(
    ("data", "code"),
    [
        pytest.param(PNG_1X1, "not_pdf", id="TC-015-png"),
        pytest.param(b"", "not_pdf", id="empty"),
        pytest.param(b" %PDF-1.4\n", "not_pdf", id="signature-not-at-start"),
        pytest.param(b"%PDF-1.4\nnot really a pdf", "pdf_unreadable", id="garbage-after-signature"),
    ],
)
def test_rejects_bad_bytes(data: bytes, code: str) -> None:
    assert _reject_code(data) == code


def test_tc018_truncated_pdf_is_unreadable() -> None:
    source = SOURCE_PDF.read_bytes()

    assert _reject_code(source[: len(source) // 2]) == "pdf_unreadable"


@pytest.mark.parametrize("user_password", ["secret", ""], ids=["TC-017-password", "empty-password"])
def test_tc017_encrypted_pdf_is_rejected(user_password: str) -> None:
    assert _reject_code(_encrypted(SOURCE_PDF.read_bytes(), user_password)) == "pdf_encrypted"
