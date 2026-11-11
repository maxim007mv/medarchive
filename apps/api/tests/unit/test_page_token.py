import base64
from typing import Any

import pytest

from app.core.errors import ErrorCode, ProblemError
from app.core.page_token import CursorValue, PageTokenCodec, list_fingerprint

CURRENT = "c" * 43
PREVIOUS = "p" * 43
CURSOR: dict[str, CursorValue] = {
    "list_key": -46119,
    "uploaded_at": "2026-11-10T16:02:11Z",
    "id": "01930c71-2a3b",
}
PARAMS: dict[str, Any] = {"q": "анализ", "type": ["analysis"], "order_by": "document_date desc"}


def _invalid(codec: PageTokenCodec, token: str, params: dict[str, Any]) -> None:
    with pytest.raises(ProblemError) as caught:
        codec.decode(token, list_fingerprint(params))
    assert caught.value.code is ErrorCode.INVALID_PAGE_TOKEN


def test_round_trip() -> None:
    codec = PageTokenCodec([CURRENT])

    token = codec.encode(CURSOR, list_fingerprint(PARAMS))

    assert codec.decode(token, list_fingerprint(dict(PARAMS))) == CURSOR
    assert "анализ" not in token


def test_token_from_other_filter_is_invalid() -> None:
    codec = PageTokenCodec([CURRENT])
    token = codec.encode(CURSOR, list_fingerprint(PARAMS))

    _invalid(codec, token, {**PARAMS, "q": "анализы"})
    _invalid(codec, token, {**PARAMS, "order_by": "uploaded_at desc"})


def test_tampered_token_is_invalid() -> None:
    codec = PageTokenCodec([CURRENT])
    raw = bytearray(base64.urlsafe_b64decode(codec.encode(CURSOR, list_fingerprint(PARAMS)) + "=="))
    raw[-1] ^= 1
    tampered = base64.urlsafe_b64encode(bytes(raw)).rstrip(b"=").decode()

    _invalid(codec, tampered, PARAMS)


@pytest.mark.parametrize("token", ["", "not-base64!", "AAAA", "x" * 600])
def test_garbage_is_invalid(token: str) -> None:
    _invalid(PageTokenCodec([CURRENT]), token, PARAMS)


def test_previous_key_still_decodes_after_rotation() -> None:
    token = PageTokenCodec([PREVIOUS]).encode(CURSOR, list_fingerprint(PARAMS))

    assert PageTokenCodec([CURRENT, PREVIOUS]).decode(token, list_fingerprint(PARAMS)) == CURSOR


def test_retired_key_is_invalid() -> None:
    token = PageTokenCodec([PREVIOUS]).encode(CURSOR, list_fingerprint(PARAMS))

    _invalid(PageTokenCodec([CURRENT]), token, PARAMS)


def test_fingerprint_ignores_key_order() -> None:
    assert list_fingerprint({"a": 1, "b": 2}) == list_fingerprint({"b": 2, "a": 1})
