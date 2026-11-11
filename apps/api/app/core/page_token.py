"""Opaque list cursors (06-api-contract, section 4; AIP-158).

Token = base64url(key id 4 | nonce 12 | AES-GCM(cursor JSON)). The fingerprint of the list
parameters is bound as AAD, so a token replayed with another `q`, filter, `tz` or `order_by`
fails authentication exactly like a tampered one: both are `invalid_page_token`.
"""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from collections.abc import Mapping, Sequence
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.errors import ErrorCode, ProblemError

_KEY_ID_BYTES = 4
_NONCE_BYTES = 12
_MAX_TOKEN_CHARS = 512

CursorValue = str | int


def list_fingerprint(params: Mapping[str, Any]) -> bytes:
    """SHA-256 of the list parameters in canonical JSON; pass every parameter of the request."""
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).digest()


class PageTokenCodec:
    def __init__(self, key_secrets: Sequence[str]) -> None:
        """`key_secrets[0]` encrypts new tokens; every listed secret still decrypts."""
        if not key_secrets:
            raise ValueError("at least one page token secret is required")
        keys = [_derive_key(secret) for secret in key_secrets]
        self._current = keys[0]
        self._by_id = {_key_id(key): AESGCM(key) for key in keys}

    def encode(self, cursor: Mapping[str, CursorValue], fingerprint: bytes) -> str:
        key_id = _key_id(self._current)
        nonce = secrets.token_bytes(_NONCE_BYTES)
        payload = json.dumps(cursor, separators=(",", ":")).encode()
        ciphertext = self._by_id[key_id].encrypt(nonce, payload, key_id + fingerprint)
        return base64.urlsafe_b64encode(key_id + nonce + ciphertext).rstrip(b"=").decode()

    def decode(self, token: str, fingerprint: bytes) -> dict[str, CursorValue]:
        """Raises `ProblemError(invalid_page_token)` for any token this list cannot continue."""
        raw = _b64decode(token) if len(token) <= _MAX_TOKEN_CHARS else None
        if raw is None or len(raw) <= _KEY_ID_BYTES + _NONCE_BYTES:
            raise ProblemError(ErrorCode.INVALID_PAGE_TOKEN)
        key_id = raw[:_KEY_ID_BYTES]
        nonce = raw[_KEY_ID_BYTES : _KEY_ID_BYTES + _NONCE_BYTES]
        cipher = self._by_id.get(key_id)
        if cipher is None:
            raise ProblemError(ErrorCode.INVALID_PAGE_TOKEN)
        try:
            payload = cipher.decrypt(
                nonce, raw[_KEY_ID_BYTES + _NONCE_BYTES :], key_id + fingerprint
            )
        except InvalidTag:
            raise ProblemError(ErrorCode.INVALID_PAGE_TOKEN) from None
        cursor: dict[str, CursorValue] = json.loads(payload)
        return cursor


def _derive_key(secret: str) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"medarchive page token")
    return hkdf.derive(secret.encode())


def _key_id(key: bytes) -> bytes:
    return hmac.digest(key, b"key id", "sha256")[:_KEY_ID_BYTES]


def _b64decode(token: str) -> bytes | None:
    try:
        return base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError):
        return None
