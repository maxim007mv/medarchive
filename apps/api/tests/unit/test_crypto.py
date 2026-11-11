import io
import secrets
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import tink
from prometheus_client import REGISTRY
from tink import aead, json_proto_keyset_format, secret_key_access

from app.core.crypto import Kek, WorkspaceKeys

SEGMENT_BYTES = 4096


def _kek_errors(operation: str) -> float:
    return REGISTRY.get_sample_value("kek_errors_total", {"operation": operation}) or 0.0


def _write_kek(path: Path) -> Path:
    handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    path.write_text(json_proto_keyset_format.serialize(handle, secret_key_access.TOKEN))
    return path


@pytest.fixture
def kek(tmp_path: Path) -> Kek:
    return Kek.from_file(_write_kek(tmp_path / "kek.json"))


@pytest.fixture
def workspace_id() -> UUID:
    return uuid4()


@pytest.fixture
def keys(kek: Kek, workspace_id: UUID) -> WorkspaceKeys:
    return kek.new_workspace_keys(workspace_id)[0]


def test_field_round_trip(keys: WorkspaceKeys) -> None:
    document_id = uuid4()

    ciphertext = keys.encrypt_field("Общий анализ крови", document_id.bytes)

    assert "Общий".encode() not in ciphertext
    assert keys.decrypt_field(ciphertext, document_id.bytes) == "Общий анализ крови"


def test_t6_ciphertext_moved_to_another_document_fails(keys: WorkspaceKeys) -> None:
    first, second = uuid4(), uuid4()
    first_title = keys.encrypt_field("Заключение терапевта", first.bytes)

    with pytest.raises(tink.TinkError):
        keys.decrypt_field(first_title, second.bytes)


def test_field_ciphertext_has_raw_prefix_sizes(keys: WorkspaceKeys) -> None:
    # ADR-047: RAW output keeps an empty value below CHECK octet_length(title_ct) >= 29.
    assert len(keys.encrypt_field("", b"aad")) == 28
    assert len(keys.encrypt_field("a", b"aad")) == 29


def test_wrapped_keys_reopen_for_the_same_workspace(kek: Kek, workspace_id: UUID) -> None:
    keys, wrapped = kek.new_workspace_keys(workspace_id)
    ciphertext = keys.encrypt_field("ЭКГ покоя", b"doc")

    reopened = kek.open_workspace_keys(wrapped, workspace_id)

    assert reopened.decrypt_field(ciphertext, b"doc") == "ЭКГ покоя"
    assert reopened.title_bidx("ЭКГ покоя") == keys.title_bidx("ЭКГ покоя")
    assert 32 <= len(wrapped) <= 1024


def test_wrapped_keys_of_another_workspace_do_not_open(kek: Kek, workspace_id: UUID) -> None:
    _, wrapped = kek.new_workspace_keys(workspace_id)

    with pytest.raises(tink.TinkError):
        kek.open_workspace_keys(wrapped, uuid4())


def test_wrapped_keys_do_not_open_with_another_kek(
    kek: Kek, workspace_id: UUID, tmp_path: Path
) -> None:
    _, wrapped = kek.new_workspace_keys(workspace_id)
    other = Kek.from_file(_write_kek(tmp_path / "other.json"))
    before = _kek_errors("open_workspace_keys")

    with pytest.raises(tink.TinkError):
        other.open_workspace_keys(wrapped, workspace_id)
    assert _kek_errors("open_workspace_keys") == before + 1


def test_unreadable_kek_file_is_counted(tmp_path: Path) -> None:
    before = _kek_errors("load_kek")

    with pytest.raises(FileNotFoundError):
        Kek.from_file(tmp_path / "missing.json")
    assert _kek_errors("load_kek") == before + 1


def test_workspaces_get_independent_keys(kek: Kek) -> None:
    first, _ = kek.new_workspace_keys(uuid4())
    second, _ = kek.new_workspace_keys(uuid4())

    assert first.title_bidx("Анализ") != second.title_bidx("Анализ")
    with pytest.raises(tink.TinkError):
        second.decrypt_field(first.encrypt_field("Анализ", b"doc"), b"doc")


def test_kek_key_id_is_primary_key_of_keyset(kek: Kek) -> None:
    assert kek.key_id.isdigit()


class _Captured(io.BytesIO):
    """Keeps the bytes readable after Tink closes the destination."""

    value = b""

    def close(self) -> None:
        self.value = self.getvalue()
        super().close()


def _encrypt_file(keys: WorkspaceKeys, plaintext: bytes, aad: bytes) -> bytes:
    destination = _Captured()
    with keys.encrypting_stream(destination, aad) as stream:
        stream.write(plaintext)
    return destination.value


def test_file_stream_round_trip_in_4kb_segments(keys: WorkspaceKeys) -> None:
    document_id = uuid4()
    plaintext = b"%PDF-1.4\n" + secrets.token_bytes(100_000)

    ciphertext = _encrypt_file(keys, plaintext, document_id.bytes)
    decrypted = keys.decrypting_stream(io.BytesIO(ciphertext), document_id.bytes).read()

    assert decrypted == plaintext
    segments = -(-len(plaintext) // (SEGMENT_BYTES - 16))
    assert len(ciphertext) - len(plaintext) < segments * 16 + 64


def test_file_stream_of_another_document_fails(keys: WorkspaceKeys) -> None:
    ciphertext = _encrypt_file(keys, b"%PDF-1.4 body", uuid4().bytes)

    with pytest.raises(tink.TinkError):
        keys.decrypting_stream(io.BytesIO(ciphertext), uuid4().bytes).read()
