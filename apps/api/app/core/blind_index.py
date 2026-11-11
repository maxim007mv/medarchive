"""Blind trigram index over encrypted titles (07-database, section 5; ADR-046).

Documents get the full `show_trgm` set: every word padded with two spaces on the left and one
on the right. Queries drop the padding on the outer edges of the query, so a substring such as
«анали» matches «анализ» in the middle of a title. Index hits are only candidates: the caller
decrypts them and confirms with `contains_query`.
"""

import hmac
import re
from collections.abc import Iterable, Iterator

# Letters and digits; everything else separates words, as in pg_trgm.
_WORD = re.compile(r"[^\W_]+")


def normalize(text: str) -> str:
    """Case- and ё-insensitive form with whitespace collapsed and trimmed."""
    return " ".join(text.lower().replace("ё", "е").split())


def document_trigrams(title: str) -> set[str]:
    return {trigram for word in _words(title) for trigram in _trigrams(f"  {word} ")}


def query_trigrams(query: str) -> set[str]:
    """Trigrams a matching title must contain; empty if the query has no letters or digits."""
    words = _words(query)
    last = len(words) - 1
    trigrams: set[str] = set()
    for position, word in enumerate(words):
        left = "" if position == 0 else "  "
        right = "" if position == last else " "
        trigrams.update(_trigrams(left + word + right))
    return trigrams


def hash_trigrams(key: bytes, trigrams: Iterable[str]) -> list[int]:
    """HMAC-SHA256 of each trigram, first 8 bytes as signed big-endian int64, sorted, unique."""
    return sorted(
        {
            int.from_bytes(hmac.digest(key, trigram.encode(), "sha256")[:8], "big", signed=True)
            for trigram in trigrams
        }
    )


def contains_query(title: str, query: str) -> bool:
    return normalize(query) in normalize(title)


def _words(text: str) -> list[str]:
    return _WORD.findall(normalize(text))


def _trigrams(padded: str) -> Iterator[str]:
    return (padded[start : start + 3] for start in range(len(padded) - 2))
