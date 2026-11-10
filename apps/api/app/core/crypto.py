"""Envelope encryption of workspace data (ADR-041, ADR-047).

Each workspace has one key bundle: a Tink AEAD keyset for fields (AES256_GCM, RAW prefix), a
Tink Streaming AEAD keyset for files (AES256_GCM_HKDF_4KB) and a 32-byte blind index key. The
bundle is stored encrypted by the KEK with AAD = workspace id, so it cannot be moved to another
workspace row. Open keys live only for one request: nothing here caches them.
"""

import secrets
import struct
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

import tink
from tink import (
    aead,
    json_proto_keyset_format,
    proto_keyset_format,
    secret_key_access,
    streaming_aead,
)

from app.core import blind_index

aead.register()
streaming_aead.register()

BLIND_INDEX_KEY_BYTES = 32
_BUNDLE_VERSION = 1
_HEADER = struct.Struct(">BH")
_LENGTH = struct.Struct(">H")


class WorkspaceKeys:
    """Open keys of one workspace. Get them per request with `Kek.open_workspace_keys`.

    AAD conventions: document fields and files use `document_id.bytes`.
    """

    __slots__ = ("_blind_index_key", "_fields", "_files")

    def __init__(
        self, fields: aead.Aead, files: streaming_aead.StreamingAead, blind_index_key: bytes
    ) -> None:
        self._fields = fields
        self._files = files
        self._blind_index_key = blind_index_key

    def encrypt_field(self, value: str, aad: bytes) -> bytes:
        ciphertext: bytes = self._fields.encrypt(value.encode(), aad)
        return ciphertext

    def decrypt_field(self, ciphertext: bytes, aad: bytes) -> str:
        """Raises `tink.TinkError` if the ciphertext belongs to another AAD or was altered."""
        plaintext: bytes = self._fields.decrypt(ciphertext, aad)
        return plaintext.decode()

    def encrypting_stream(self, destination: BinaryIO, aad: bytes) -> BinaryIO:
        """Writable stream; closing it writes the final segment and closes `destination`."""
        stream: BinaryIO = self._files.new_encrypting_stream(destination, aad)
        return stream

    def decrypting_stream(self, source: BinaryIO, aad: bytes) -> BinaryIO:
        """Readable, not seekable (Tink 1.16): ranges are served by reading and skipping."""
        stream: BinaryIO = self._files.new_decrypting_stream(source, aad)
        return stream

    def title_bidx(self, title: str) -> list[int]:
        """Value for `documents.title_bidx`."""
        return blind_index.hash_trigrams(
            self._blind_index_key, blind_index.document_trigrams(title)
        )

    def query_bidx(self, query: str) -> list[int]:
        """Hashes for `title_bidx @> :hashes`; confirm hits with `blind_index.contains_query`."""
        return blind_index.hash_trigrams(self._blind_index_key, blind_index.query_trigrams(query))


class Kek:
    """Key encryption key from a cleartext Tink AEAD keyset file (local stand-in for KMS)."""

    def __init__(self, handle: tink.KeysetHandle) -> None:
        self._aead: aead.Aead = handle.primitive(aead.Aead)
        self.key_id = str(handle.keyset_info().primary_key_id)

    @classmethod
    def from_file(cls, path: Path) -> "Kek":
        handle = json_proto_keyset_format.parse(path.read_text(), secret_key_access.TOKEN)
        return cls(handle)

    def new_workspace_keys(self, workspace_id: UUID) -> tuple[WorkspaceKeys, bytes]:
        """Fresh keys and their wrapped form for `workspaces.dek_ciphertext`."""
        fields = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM_RAW)
        files = tink.new_keyset_handle(
            streaming_aead.streaming_aead_key_templates.AES256_GCM_HKDF_4KB
        )
        blind_index_key = secrets.token_bytes(BLIND_INDEX_KEY_BYTES)
        bundle = _pack(_serialize(fields), _serialize(files), blind_index_key)
        wrapped: bytes = self._aead.encrypt(bundle, workspace_id.bytes)
        return _open(fields, files, blind_index_key), wrapped

    def open_workspace_keys(self, wrapped: bytes, workspace_id: UUID) -> WorkspaceKeys:
        """Raises `tink.TinkError` for a bundle of another workspace or another KEK."""
        bundle: bytes = self._aead.decrypt(wrapped, workspace_id.bytes)
        fields, files, blind_index_key = _unpack(bundle)
        return _open(
            proto_keyset_format.parse(fields, secret_key_access.TOKEN),
            proto_keyset_format.parse(files, secret_key_access.TOKEN),
            blind_index_key,
        )


def _open(
    fields: tink.KeysetHandle, files: tink.KeysetHandle, blind_index_key: bytes
) -> WorkspaceKeys:
    return WorkspaceKeys(
        fields.primitive(aead.Aead),
        files.primitive(streaming_aead.StreamingAead),
        blind_index_key,
    )


def _serialize(handle: tink.KeysetHandle) -> bytes:
    serialized: bytes = proto_keyset_format.serialize(handle, secret_key_access.TOKEN)
    return serialized


def _pack(fields: bytes, files: bytes, blind_index_key: bytes) -> bytes:
    return b"".join(
        (
            _HEADER.pack(_BUNDLE_VERSION, len(fields)),
            fields,
            _LENGTH.pack(len(files)),
            files,
            blind_index_key,
        )
    )


def _unpack(bundle: bytes) -> tuple[bytes, bytes, bytes]:
    version, fields_length = _HEADER.unpack_from(bundle)
    if version != _BUNDLE_VERSION:
        raise tink.TinkError(f"unsupported key bundle version {version}")
    fields_end = _HEADER.size + fields_length
    (files_length,) = _LENGTH.unpack_from(bundle, fields_end)
    files_start = fields_end + _LENGTH.size
    files_end = files_start + files_length
    if len(bundle) != files_end + BLIND_INDEX_KEY_BYTES:
        raise tink.TinkError("malformed key bundle")
    return bundle[_HEADER.size : fields_end], bundle[files_start:files_end], bundle[files_end:]
