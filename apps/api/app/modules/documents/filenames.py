"""File names for downloads and exports (docs/texts.md, section 13 «Экспорт»)."""

import re
from collections.abc import Iterable, Iterator
from datetime import date
from urllib.parse import quote

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}  # fmt: skip
ASCII_LETTERS_AND_DIGITS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789")
MAX_SLUG_CHARS = 80
EMPTY_SLUG = "dokument"
UNDATED_PREFIX = "bez-daty"
# Keeps the UTF-8 name of 200 Cyrillic characters under the 255-byte limit of common file systems.
MAX_DISPLAY_TITLE_CHARS = 100
UNSAFE_IN_FILE_NAME = re.compile(r'[\x00-\x1f\x7f/\\:*?"<>|]')


def slugify(title: str) -> str:
    """Lowercase transliterated title: Latin letters and digits kept, anything else becomes `-`."""
    chars = (
        ch if ch in ASCII_LETTERS_AND_DIGITS else TRANSLIT.get(ch, "-") for ch in title.lower()
    )
    slug = re.sub("-{2,}", "-", "".join(chars)).strip("-")
    if len(slug) > MAX_SLUG_CHARS:
        slug = _cut_at_word_boundary(slug)
    return slug or EMPTY_SLUG


def _cut_at_word_boundary(slug: str) -> str:
    head = slug[: MAX_SLUG_CHARS + 1]
    boundary = head.rfind("-")
    return slug[:boundary] if boundary > 0 else slug[:MAX_SLUG_CHARS]


def date_prefix(document_date: date | None) -> str:
    return document_date.isoformat() if document_date else UNDATED_PREFIX


def pdf_file_name(title: str, document_date: date | None) -> str:
    """ASCII name `{YYYY-MM-DD|bez-daty}_{slug}.pdf`."""
    return f"{date_prefix(document_date)}_{slugify(title)}.pdf"


def unique_names(names: Iterable[str]) -> Iterator[str]:
    """Yield names in order; repeats get `-2`, `-3`, ... before the extension."""
    used: set[str] = set()
    for name in names:
        stem, dot, extension = name.rpartition(".")
        candidate, suffix = name, 1
        while candidate in used:
            suffix += 1
            candidate = f"{stem}-{suffix}{dot}{extension}"
        used.add(candidate)
        yield candidate


def content_disposition(disposition: str, title: str, document_date: date | None) -> str:
    """`inline|attachment`, ASCII `filename` and the readable title in `filename*` (RFC 6266)."""
    display_title = UNSAFE_IN_FILE_NAME.sub("_", title)[:MAX_DISPLAY_TITLE_CHARS]
    utf8_name = f"{date_prefix(document_date)}_{display_title}.pdf"
    return (
        f'{disposition}; filename="{pdf_file_name(title, document_date)}"; '
        f"filename*=UTF-8''{quote(utf8_name, safe='')}"
    )
