"""Checks a quarantined upload before it becomes a document: signature, pypdf parse, encryption."""

from typing import BinaryIO, Literal

from pypdf import PasswordType, PdfReader

PDF_SIGNATURE = b"%PDF-"
# CHECK on document_files.page_count; a longer file is stored without a page count.
MAX_STORED_PAGE_COUNT = 2000

PdfRejectCode = Literal["not_pdf", "pdf_unreadable", "pdf_encrypted"]


class PdfRejectedError(Exception):
    """The file is not an acceptable PDF; `code` is the API error code and `uploads.reject_code`."""

    def __init__(self, code: PdfRejectCode) -> None:
        super().__init__(code)
        self.code: PdfRejectCode = code


def inspect_pdf(stream: BinaryIO) -> int | None:
    """Return the page count of a PDF that opens without a password, or None if it exceeds what
    the schema stores. A PDF with only an owner password (no printing or editing) opens and is
    accepted as is.

    Raises PdfRejectedError: `not_pdf` without the `%PDF-` signature at offset 0, `pdf_encrypted`
    when a user password is needed to open it, `pdf_unreadable` when pypdf fails.
    """
    stream.seek(0)
    if stream.read(len(PDF_SIGNATURE)) != PDF_SIGNATURE:
        raise PdfRejectedError("not_pdf")
    stream.seek(0)
    try:
        reader = PdfReader(stream)
        needs_password = reader.is_encrypted and (reader.decrypt("") == PasswordType.NOT_DECRYPTED)
        page_count = 0 if needs_password else len(reader.pages)
    # pypdf raises arbitrary exception types (KeyError, ValueError, RecursionError, ...) on
    # malformed input, and every one of them means the same thing for an upload.
    except Exception as exc:
        raise PdfRejectedError("pdf_unreadable") from exc
    if needs_password:
        raise PdfRejectedError("pdf_encrypted")
    if page_count == 0:
        raise PdfRejectedError("pdf_unreadable")
    return page_count if page_count <= MAX_STORED_PAGE_COUNT else None
