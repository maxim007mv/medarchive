import secrets

import pytest

from app.core.blind_index import (
    contains_query,
    document_trigrams,
    hash_trigrams,
    normalize,
    query_trigrams,
)

KEY = secrets.token_bytes(32)
TITLE = "Общий анализ крови"


def _index_hit(title: str, query: str) -> bool:
    title_hashes = set(hash_trigrams(KEY, document_trigrams(title)))
    return set(hash_trigrams(KEY, query_trigrams(query))) <= title_hashes


def _found(title: str, query: str) -> bool:
    return _index_hit(title, query) and contains_query(title, query)


def test_normalize_lowercases_replaces_yo_and_collapses_spaces() -> None:
    assert normalize("  ЁЖ   Ёлка\tи\nёж ") == "еж елка и еж"


def test_document_trigrams_follow_show_trgm_padding() -> None:
    # SELECT show_trgm('кот') = {"  к"," ко","кот","от "}
    assert document_trigrams("Кот") == {"  к", " ко", "кот", "от "}
    assert document_trigrams("a, b") == {"  a", " a ", "  b", " b "}


def test_query_trigrams_drop_outer_padding() -> None:
    assert query_trigrams("анали") == {"ана", "нал", "али"}
    assert query_trigrams("ий анал") == {"ий ", "  а", " ан", "ана", "нал"}


@pytest.mark.parametrize(
    "query", ["анали", "нализ", "ий анал", "АНАЛИЗ", "анализ", "общий анализ крови", "Крови"]
)
def test_substring_queries_find_title(query: str) -> None:
    assert _found(TITLE, query)


def test_yo_and_ye_are_the_same_letter() -> None:
    assert _found("Отчёт врача", "отчет")
    assert _found("Отчет врача", "ОТЧЁТ")


@pytest.mark.parametrize("query", ["анемия", "кровь", "анализ мочи"])
def test_absent_substring_is_not_found(query: str) -> None:
    assert not _found(TITLE, query)


def test_trigrams_in_different_words_are_rejected_by_substring_check() -> None:
    # ADR-046: every trigram of «анали» is present, but the substring is not.
    assert _index_hit("ана нал али", "анали")
    assert not contains_query("ана нал али", "анали")


def test_hashes_are_signed_int64_sorted_and_unique() -> None:
    hashes = hash_trigrams(KEY, document_trigrams("анализ анализ"))

    assert hashes == sorted(set(hashes))
    assert all(-(2**63) <= value < 2**63 for value in hashes)
    assert len(hashes) == len(document_trigrams("анализ"))


def test_hashes_depend_on_key() -> None:
    trigrams = document_trigrams(TITLE)

    assert hash_trigrams(KEY, trigrams) != hash_trigrams(secrets.token_bytes(32), trigrams)


def test_query_without_letters_or_digits_has_no_trigrams() -> None:
    assert query_trigrams("+++") == set()
