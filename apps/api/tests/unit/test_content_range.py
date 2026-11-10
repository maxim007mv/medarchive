from io import BytesIO

import pytest

from app.modules.documents.content import CHUNK_BYTES, ByteRange, iter_bytes, parse_range

SIZE = 79114


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("bytes=0-65535", ByteRange(0, 65535)),
        ("bytes=65536-", ByteRange(65536, SIZE - 1)),
        ("bytes=-100", ByteRange(SIZE - 100, SIZE - 1)),
        ("bytes=-999999", ByteRange(0, SIZE - 1)),
        ("bytes=79000-999999", ByteRange(79000, SIZE - 1)),
        ("bytes=5-5", ByteRange(5, 5)),
    ],
)
def test_satisfiable_ranges(header: str, expected: ByteRange) -> None:
    assert parse_range(header, SIZE) == expected


@pytest.mark.parametrize(
    "header",
    [None, "", "bytes=", "bytes=-", "bytes=-0", "bytes=10-5", "bytes=79114-", "items=0-1",
     "bytes=0-1,5-6", "bytes=a-b"],
)  # fmt: skip
def test_ignored_ranges_mean_full_body(header: str | None) -> None:
    assert parse_range(header, SIZE) is None


def test_content_range_header() -> None:
    assert ByteRange(0, 65535).content_range(SIZE) == "bytes 0-65535/79114"


def _collect(data: bytes, byte_range: ByteRange | None) -> bytes:
    return b"".join(iter_bytes(BytesIO(data), byte_range))


DATA = bytes(range(256)) * 50


@pytest.mark.parametrize(
    "byte_range",
    [
        ByteRange(0, 0),
        ByteRange(0, len(DATA) - 1),
        ByteRange(CHUNK_BYTES - 1, CHUNK_BYTES),
        ByteRange(CHUNK_BYTES, 2 * CHUNK_BYTES - 1),
        ByteRange(5000, 9000),
        ByteRange(len(DATA) - 3, len(DATA) - 1),
    ],
)
def test_iter_bytes_returns_exact_slice(byte_range: ByteRange) -> None:
    assert _collect(DATA, byte_range) == DATA[byte_range.start : byte_range.end + 1]


def test_iter_bytes_whole_stream_and_closes_it() -> None:
    stream = BytesIO(DATA)

    assert b"".join(iter_bytes(stream, None)) == DATA
    assert stream.closed
