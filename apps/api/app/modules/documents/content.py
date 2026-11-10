"""Byte ranges over a decrypting stream that cannot seek (Tink 1.16, ADR-047)."""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import IO

# One segment of AES256_GCM_HKDF_4KB: Tink releases plaintext only per authenticated segment.
CHUNK_BYTES = 4096
_SINGLE_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int  # inclusive

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    def content_range(self, size: int) -> str:
        return f"bytes {self.start}-{self.end}/{size}"


def parse_range(header: str | None, size: int) -> ByteRange | None:
    """Single satisfiable range, or None to answer 200 with the whole file.

    RFC 9110 lets a server ignore Range, so multipart, malformed and unsatisfiable ranges are
    served in full rather than with 416, which the contract does not declare.
    """
    match = _SINGLE_RANGE.match((header or "").strip())
    if not match or size == 0:
        return None
    first, last = match.groups()
    if not first:
        if not last or int(last) == 0:
            return None
        return ByteRange(max(size - int(last), 0), size - 1)
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        return None
    return ByteRange(start, end)


def iter_bytes(stream: IO[bytes], byte_range: ByteRange | None) -> Iterator[bytes]:
    """Read sequentially, skip up to the range start, stop after its end; closes the stream."""
    start, remaining = (byte_range.start, byte_range.length) if byte_range else (0, None)
    with stream:
        while remaining is None or remaining > 0:
            chunk = stream.read(CHUNK_BYTES)
            if not chunk:
                return
            if start >= len(chunk):
                start -= len(chunk)
                continue
            chunk = chunk[start:]
            start = 0
            if remaining is not None:
                chunk = chunk[:remaining]
                remaining -= len(chunk)
            yield chunk
