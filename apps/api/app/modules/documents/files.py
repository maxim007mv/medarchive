"""PDF bytes between storage and the API: verify and encrypt on create, decrypt on read.

Synchronous (boto3 and Tink streams): callers run `store_verified_pdf` and `open_plaintext` in a
worker thread, and Starlette iterates the returned chunks in its thread pool.
"""

import hashlib
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from app.core.crypto import WorkspaceKeys
from app.core.errors import ErrorCode, ProblemError
from app.modules.documents.content import ByteRange, iter_bytes
from app.modules.uploads.pdf import inspect_pdf
from app.modules.uploads.schemas import MAX_UPLOAD_BYTES
from app.storage.s3 import ObjectStorage

_COPY_BUFFER_BYTES = 64 * 1024


@dataclass(frozen=True)
class StoredFile:
    size_bytes: int
    sha256: bytes
    page_count: int | None


def store_verified_pdf(
    storage: ObjectStorage,
    keys: WorkspaceKeys,
    *,
    quarantine_key: str,
    object_key: str,
    document_id: UUID,
) -> StoredFile:
    """Check the quarantined upload and write its ciphertext (AAD = document id) to `ma-docs`.

    Raises PdfRejectedError for a bad file, ProblemError(file_too_large) if the object exceeds
    the limit despite the POST policy, StorageUnavailableError if storage fails.
    """
    with tempfile.TemporaryDirectory(prefix="upload-") as workdir:
        plain_path, cipher_path = Path(workdir, "plain"), Path(workdir, "cipher")
        with plain_path.open("w+b") as plain:
            storage.quarantine.download(quarantine_key, plain)
            size_bytes = plain.tell()
            if size_bytes > MAX_UPLOAD_BYTES:
                raise ProblemError(ErrorCode.FILE_TOO_LARGE)
            page_count = inspect_pdf(plain)
            plain.seek(0)
            sha256 = hashlib.file_digest(plain, "sha256").digest()
            plain.seek(0)
            # Tink closes the destination when the encrypting stream closes.
            with keys.encrypting_stream(cipher_path.open("wb"), document_id.bytes) as encrypted:
                shutil.copyfileobj(plain, encrypted, _COPY_BUFFER_BYTES)
        with cipher_path.open("rb") as ciphertext:
            storage.docs.upload(object_key, ciphertext)
    return StoredFile(size_bytes=size_bytes, sha256=sha256, page_count=page_count)


def iter_plaintext(
    storage: ObjectStorage, keys: WorkspaceKeys, *, object_key: str, document_id: UUID
) -> Iterator[bytes]:
    """Decrypted file, opened lazily on first iteration: a ZIP holds one object open at a time."""
    yield from _decrypted(storage.docs.open(object_key), keys, document_id, None)


def open_plaintext(
    storage: ObjectStorage,
    keys: WorkspaceKeys,
    *,
    object_key: str,
    document_id: UUID,
    byte_range: ByteRange | None,
) -> Iterator[bytes]:
    """Decrypted file or range, opened now: storage failure is a 503 before the response starts."""
    return _decrypted(storage.docs.open(object_key), keys, document_id, byte_range)


def _decrypted(
    body: BinaryIO, keys: WorkspaceKeys, document_id: UUID, byte_range: ByteRange | None
) -> Iterator[bytes]:
    try:
        yield from iter_bytes(keys.decrypting_stream(body, document_id.bytes), byte_range)
    finally:
        body.close()
