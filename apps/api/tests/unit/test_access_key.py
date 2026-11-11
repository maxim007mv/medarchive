import re

import pytest

from app.modules.auth.access_key import (
    AccessKey,
    generate_access_key,
    hash_secret,
    parse_access_key,
    verify_secret,
)

KEY = "7K3M-Q9TB-2XRA-HC4D-P8WN-6YFE"
# WorkspaceCreated.access_key in openapi.yaml
PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{4}(-[0-9A-HJKMNP-TV-Z]{4}){5}$")


def test_generated_key_has_contract_format() -> None:
    key = generate_access_key()

    assert PATTERN.fullmatch(key.display)
    assert len(key.lookup_id) == 6
    assert len(key.secret) == 18


def test_generated_keys_differ() -> None:
    assert len({generate_access_key().display for _ in range(100)}) == 100


@pytest.mark.parametrize(
    "typed",
    [
        KEY,
        KEY.replace("-", ""),
        KEY.lower(),
        "7k3m q9tb 2xra hc4d p8wn 6yfe",
    ],
)
def test_parse_accepts_dashes_spaces_and_lowercase(typed: str) -> None:
    assert parse_access_key(typed) == AccessKey("7K3MQ9", "TB2XRAHC4DP8WN6YFE")


def test_parse_reads_crockford_lookalikes() -> None:
    parsed = parse_access_key("OOOOOO-IIIIII-LLLLLL-oooooo")

    assert parsed == AccessKey("000000", "111111111111000000")


@pytest.mark.parametrize(
    "typed",
    ["", KEY[:-1], KEY + "Z", KEY.replace("7", "U"), KEY.replace("7", "*"), "Ё" * 24],
)
def test_parse_rejects_non_keys(typed: str) -> None:
    assert parse_access_key(typed) is None


def test_display_round_trips_through_parse() -> None:
    key = generate_access_key()

    assert parse_access_key(key.display) == key


def test_hash_is_argon2id_with_contract_parameters() -> None:
    hashed = hash_secret("TB2XRAHC4DP8WN6YFE")

    assert hashed.startswith("$argon2id$v=19$m=19456,t=2,p=1$")


def test_verify_accepts_only_the_right_secret() -> None:
    hashed = hash_secret("TB2XRAHC4DP8WN6YFE")

    assert verify_secret(hashed, "TB2XRAHC4DP8WN6YFE")
    assert not verify_secret(hashed, "TB2XRAHC4DP8WN6YFF")


def test_unknown_lookup_id_never_verifies() -> None:
    assert not verify_secret(None, "TB2XRAHC4DP8WN6YFE")
