import hashlib
import io
from pathlib import Path
from uuid import uuid4

import pytest
import tink
from tink import aead

from app.core.crypto import Kek, WorkspaceKeys
from app.core.errors import ErrorCode, ProblemError
from app.modules.documents.content import ByteRange
from app.modules.documents.files import iter_plaintext, open_plaintext, store_verified_pdf
from app.modules.uploads.pdf import PdfRejectedError
from app.storage.s3 import ObjectStorage

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_PDF = (REPO_ROOT / "MedArchive/05_qa/fixtures/01-general-blood-test.pdf").read_bytes()


@pytest.fixture
def keys() -> WorkspaceKeys:
    aead.register()
    kek = Kek(tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM))
    workspace_keys, _ = kek.new_workspace_keys(uuid4())
    return workspace_keys


def _store(storage: ObjectStorage, keys: WorkspaceKeys, data: bytes) -> tuple[str, str]:
    quarantine_key, object_key = f"q/{uuid4()}.bin", f"ws/{uuid4()}.bin"
    storage.quarantine.upload(quarantine_key, io.BytesIO(data))
    return quarantine_key, object_key


def test_tc057_stored_file_decrypts_to_identical_bytes(
    storage: ObjectStorage, keys: WorkspaceKeys
) -> None:
    quarantine_key, object_key = _store(storage, keys, SOURCE_PDF)
    document_id = uuid4()

    stored = store_verified_pdf(
        storage, keys, quarantine_key=quarantine_key, object_key=object_key, document_id=document_id
    )

    assert stored.size_bytes == len(SOURCE_PDF)
    assert stored.sha256 == hashlib.sha256(SOURCE_PDF).digest()
    assert stored.page_count == 1
    with storage.docs.open(object_key) as body:
        ciphertext = body.read()
    assert b"%PDF-" not in ciphertext
    plain = b"".join(iter_plaintext(storage, keys, object_key=object_key, document_id=document_id))
    assert hashlib.sha256(plain).digest() == stored.sha256


def test_range_of_stored_file(storage: ObjectStorage, keys: WorkspaceKeys) -> None:
    quarantine_key, object_key = _store(storage, keys, SOURCE_PDF)
    document_id = uuid4()
    store_verified_pdf(
        storage, keys, quarantine_key=quarantine_key, object_key=object_key, document_id=document_id
    )

    part = b"".join(
        open_plaintext(
            storage,
            keys,
            object_key=object_key,
            document_id=document_id,
            byte_range=ByteRange(10_000, 75_535),
        )
    )

    assert part == SOURCE_PDF[10_000:75_536]


def test_ciphertext_is_bound_to_document_id(storage: ObjectStorage, keys: WorkspaceKeys) -> None:
    quarantine_key, object_key = _store(storage, keys, SOURCE_PDF)
    store_verified_pdf(
        storage, keys, quarantine_key=quarantine_key, object_key=object_key, document_id=uuid4()
    )

    with pytest.raises(tink.TinkError):
        b"".join(iter_plaintext(storage, keys, object_key=object_key, document_id=uuid4()))


def test_rejected_pdf_writes_nothing(storage: ObjectStorage, keys: WorkspaceKeys) -> None:
    quarantine_key, object_key = _store(storage, keys, b"\x89PNG\r\n\x1a\n")

    with pytest.raises(PdfRejectedError) as exc_info:
        store_verified_pdf(
            storage, keys, quarantine_key=quarantine_key, object_key=object_key, document_id=uuid4()
        )

    assert exc_info.value.code == "not_pdf"
    assert storage.docs.size(object_key) is None


def test_object_over_limit_is_file_too_large(
    storage: ObjectStorage, keys: WorkspaceKeys, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.modules.documents.files.MAX_UPLOAD_BYTES", len(SOURCE_PDF) - 1)
    quarantine_key, object_key = _store(storage, keys, SOURCE_PDF)

    with pytest.raises(ProblemError) as exc_info:
        store_verified_pdf(
            storage, keys, quarantine_key=quarantine_key, object_key=object_key, document_id=uuid4()
        )

    assert exc_info.value.code is ErrorCode.FILE_TOO_LARGE
