import io
import secrets
import tempfile
import tracemalloc

import httpx
import pytest

from app.storage.s3 import ObjectStorage, StorageUnavailableError

QUARANTINE, DOCS = "ma-quarantine", "ma-docs"


def _browser_post(storage: ObjectStorage, key: str, body: bytes, *, max_bytes: int) -> int:
    post = storage.presign_quarantine_upload(key, max_bytes=max_bytes, expires_in_seconds=900)
    response = httpx.post(post.url, data=post.fields, files={"file": ("x.pdf", body)})
    return response.status_code


def test_presigned_post_uploads_exact_key(storage: ObjectStorage) -> None:
    assert _browser_post(storage, "q/ws/a.bin", b"%PDF-1.4 body", max_bytes=100) == 204

    assert storage.quarantine.size("q/ws/a.bin") == len(b"%PDF-1.4 body")


def test_presigned_post_policy_fields(storage: ObjectStorage) -> None:
    post = storage.presign_quarantine_upload(
        "q/ws/b.bin", max_bytes=20971520, expires_in_seconds=900
    )

    assert post.url.endswith(f"/{QUARANTINE}")
    assert post.fields["key"] == "q/ws/b.bin"
    assert post.fields["Content-Type"] == "application/pdf"
    assert post.fields["x-amz-algorithm"] == "AWS4-HMAC-SHA256"
    assert {"policy", "x-amz-credential", "x-amz-date", "x-amz-signature"} <= post.fields.keys()


def test_presigned_post_rejects_body_over_limit(storage: ObjectStorage) -> None:
    status = _browser_post(storage, "q/ws/big.bin", b"x" * 11, max_bytes=10)

    assert status in {400, 403}
    assert storage.quarantine.size("q/ws/big.bin") is None


def test_presigned_post_rejects_other_key(storage: ObjectStorage) -> None:
    post = storage.presign_quarantine_upload("q/ws/c.bin", max_bytes=100, expires_in_seconds=900)
    fields = {**post.fields, "key": "q/other/c.bin"}

    response = httpx.post(post.url, data=fields, files={"file": ("x.pdf", b"%PDF-")})

    assert response.status_code == 403
    assert storage.quarantine.size("q/other/c.bin") is None


def test_upload_open_list_delete_roundtrip(storage: ObjectStorage) -> None:
    payload = bytes(range(256)) * 100
    storage.docs.upload("ws/1/doc.bin", io.BytesIO(payload))

    with storage.docs.open("ws/1/doc.bin") as body:
        assert body.read() == payload
    assert [item.key for item in storage.docs.list("ws/1/")] == ["ws/1/doc.bin"]

    storage.docs.delete("ws/1/doc.bin")
    storage.docs.delete("ws/1/doc.bin")
    assert storage.docs.size("ws/1/doc.bin") is None
    assert list(storage.docs.list("ws/1/")) == []


def test_upload_of_20_mib_file_streams_from_disk(storage: ObjectStorage) -> None:
    with tempfile.TemporaryFile() as source:
        source.write(bytes(20 * 1024 * 1024))
        source.seek(0)
        tracemalloc.start()
        try:
            storage.docs.upload("ws/1/big.bin", source)
            _, peak_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

    assert storage.docs.size("ws/1/big.bin") == 20 * 1024 * 1024
    assert peak_bytes < 8 * 1024 * 1024


def test_download_to_file(storage: ObjectStorage) -> None:
    storage.quarantine.upload("q/ws/d.bin", io.BytesIO(b"%PDF-data"))
    destination = io.BytesIO()

    storage.quarantine.download("q/ws/d.bin", destination)

    assert destination.getvalue() == b"%PDF-data"


def test_unreachable_storage_is_unavailable() -> None:
    dead = ObjectStorage(
        endpoint="http://127.0.0.1:1",
        public_endpoint="http://127.0.0.1:1",
        access_key="unused",
        secret_key=secrets.token_hex(8),
        quarantine_bucket=QUARANTINE,
        docs_bucket=DOCS,
    )

    with pytest.raises(StorageUnavailableError) as exc_info:
        dead.quarantine.size("q/x.bin")
    assert exc_info.value.headers == {"Retry-After": "60"}
