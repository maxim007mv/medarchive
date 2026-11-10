import secrets
import time
from uuid import UUID

_VERSION_7 = 0x7 << 76
_VARIANT_RFC = 0b10 << 62


def new_id() -> UUID:
    """UUIDv7 (RFC 9562): 48-bit Unix milliseconds, then 74 random bits (06-api-contract, A5)."""
    unix_ms = time.time_ns() // 1_000_000
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    return UUID(int=(unix_ms << 80) | _VERSION_7 | (rand_a << 64) | _VARIANT_RFC | rand_b)
