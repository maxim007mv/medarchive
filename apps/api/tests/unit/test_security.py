import hashlib
import re
from pathlib import Path
from uuid import uuid4

from app.core.security import csrf_token, csrf_valid, new_session_token, session_token_sha256
from app.modules.auth.consent import EVIDENCE_SHA256, POLICY_VERSION

REPO = Path(__file__).resolve().parents[4]
SECRET = "s" * 43


def test_session_token_is_256_bits_and_only_its_hash_is_kept() -> None:
    cookie, digest = new_session_token()

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", cookie)
    assert session_token_sha256(cookie) == digest
    assert len(digest) == 32


def test_malformed_cookie_has_no_hash() -> None:
    assert session_token_sha256("short") is None
    assert session_token_sha256("!" * 43) is None


def test_csrf_token_is_bound_to_session() -> None:
    session_id = uuid4()
    token = csrf_token(SECRET, session_id)

    assert csrf_valid(SECRET, session_id, token)
    assert not csrf_valid(SECRET, uuid4(), token)
    assert not csrf_valid("x" * 43, session_id, token)
    assert not csrf_valid(SECRET, session_id, None)
    assert not csrf_valid(SECRET, session_id, "")
    # A different last character: "A" alone would equal the token one time in 16.
    assert not csrf_valid(SECRET, session_id, token[:-1] + ("B" if token[-1] == "A" else "A"))


def test_consent_evidence_matches_shown_texts() -> None:
    texts = (REPO / "docs/texts.md").read_text()
    match = re.search(r"^\| `onboarding\.consent\.label` \| (.+?) \|", texts, re.MULTILINE)
    assert match
    policy = (REPO / "docs/policy.md").read_bytes()
    assert f"Версия: {POLICY_VERSION}".encode() in policy

    shown = f"{POLICY_VERSION}\n{match.group(1)}\n".encode() + policy

    assert hashlib.sha256(shown).digest() == EVIDENCE_SHA256
