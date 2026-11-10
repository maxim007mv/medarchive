"""Access key: 24 Crockford Base32 characters = 6-character lookup id + 18-character secret
(90 bits). Only an Argon2id hash of the secret is stored (06-api-contract, section 2).
"""

import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LOOKUP_LENGTH = 6
SECRET_LENGTH = 18
_GROUP = 4
# Crockford decoding: case-insensitive, I and L read as 1, O as 0; separators are ignored.
_DECODE = str.maketrans({"I": "1", "L": "1", "O": "0", "-": None, " ": None})

_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


@dataclass(frozen=True, slots=True)
class AccessKey:
    lookup_id: str
    secret: str

    @property
    def display(self) -> str:
        """Six groups of four: `7K3M-Q9TB-2XRA-HC4D-P8WN-6YFE`."""
        raw = self.lookup_id + self.secret
        return "-".join(raw[start : start + _GROUP] for start in range(0, len(raw), _GROUP))


def generate_access_key() -> AccessKey:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(LOOKUP_LENGTH + SECRET_LENGTH))
    return AccessKey(lookup_id=raw[:LOOKUP_LENGTH], secret=raw[LOOKUP_LENGTH:])


def parse_access_key(text: str) -> AccessKey | None:
    """Key as typed by a person (dashes optional, any case), or None if it cannot be a key."""
    raw = text.upper().translate(_DECODE)
    if len(raw) != LOOKUP_LENGTH + SECRET_LENGTH or any(char not in ALPHABET for char in raw):
        return None
    return AccessKey(lookup_id=raw[:LOOKUP_LENGTH], secret=raw[LOOKUP_LENGTH:])


def hash_secret(secret: str) -> str:
    """Argon2id m=19 MiB, t=2, p=1. CPU-bound for tens of milliseconds: call in a thread."""
    return _HASHER.hash(secret)


def verify_secret(secret_hash: str | None, secret: str) -> bool:
    """Same work whether or not the key exists: an unknown lookup id checks a dummy hash."""
    try:
        _HASHER.verify(secret_hash or _DUMMY_HASH, secret)
    except (VerificationError, InvalidHashError):
        return False
    return secret_hash is not None


# Computed at import so the first unknown key is not slower than the rest.
_DUMMY_HASH = _HASHER.hash(secrets.token_urlsafe(SECRET_LENGTH))
