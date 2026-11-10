"""Session token and CSRF primitives (06-api-contract, section 2; ADR-047)."""

import base64
import binascii
import hashlib
import hmac
import secrets
from uuid import UUID

SESSION_COOKIE = "__Host-ma_sid"
CSRF_HEADER = "X-CSRF-Token"
_SESSION_TOKEN_BYTES = 32


def new_session_token() -> tuple[str, bytes]:
    """256-bit token for the cookie and its SHA-256, the only form the database stores."""
    token = secrets.token_bytes(_SESSION_TOKEN_BYTES)
    return _b64encode(token), hashlib.sha256(token).digest()


def session_token_sha256(cookie: str) -> bytes | None:
    """SHA-256 of a cookie value, or None if it cannot be a token we issued."""
    try:
        token = base64.urlsafe_b64decode(cookie + "=" * (-len(cookie) % 4))
    except (binascii.Error, ValueError):
        return None
    if len(token) != _SESSION_TOKEN_BYTES:
        return None
    return hashlib.sha256(token).digest()


def csrf_token(secret: str, session_id: UUID) -> str:
    """HMAC-SHA256 of the session id: no storage, changes with every new session."""
    return _b64encode(hmac.digest(secret.encode(), session_id.bytes, "sha256"))


def csrf_valid(secret: str, session_id: UUID, presented: str | None) -> bool:
    if not presented:
        return False
    return hmac.compare_digest(csrf_token(secret, session_id).encode(), presented.encode())


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
