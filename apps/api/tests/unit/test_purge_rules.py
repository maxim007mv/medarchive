from datetime import timedelta
from uuid import uuid4

import pytest

from app.workers.purge import MAX_RETRY_DELAY, parse_object_key, retry_delay


def test_parse_document_object_key() -> None:
    workspace_id, document_id = uuid4(), uuid4()

    assert parse_object_key(f"ws/{workspace_id}/{document_id}.bin") == (workspace_id, document_id)


@pytest.mark.parametrize(
    "key",
    [
        "q/a/b.bin",
        "ws/not-a-uuid/x.bin",
        f"ws/{uuid4()}/{uuid4()}.pdf",
        f"ws/{uuid4()}",
        "ws//.bin",
    ],
)
def test_foreign_keys_are_not_documents(key: str) -> None:
    assert parse_object_key(key) is None


@pytest.mark.parametrize(
    ("attempts", "expected"),
    [(1, timedelta(minutes=1)), (2, timedelta(minutes=2)), (5, timedelta(minutes=16))],
)
def test_retry_delay_doubles(attempts: int, expected: timedelta) -> None:
    assert retry_delay(attempts) == expected


def test_retry_delay_is_capped() -> None:
    assert retry_delay(30) == MAX_RETRY_DELAY
