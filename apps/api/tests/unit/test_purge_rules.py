import itertools
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.storage.s3 import StoredObject
from app.workers.purge import (
    BATCH_SIZE,
    MAX_RETRY_DELAY,
    orphan_candidates,
    parse_object_key,
    retry_delay,
)

CUTOFF = datetime(2026, 11, 11, 12, tzinfo=UTC)
OLD = CUTOFF - timedelta(hours=2)


def _document(workspace_id: UUID, modified: datetime = OLD) -> StoredObject:
    return StoredObject(key=f"ws/{workspace_id}/{uuid4()}.bin", last_modified=modified)


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


def test_orphan_candidates_read_the_listing_one_batch_at_a_time() -> None:
    workspace_id = uuid4()
    listed = 0

    def endless_listing() -> Iterator[StoredObject]:
        nonlocal listed
        while True:
            listed += 1
            yield _document(workspace_id)

    first_workspace, first_batch = next(orphan_candidates(endless_listing(), CUTOFF))

    assert first_workspace == workspace_id
    assert len(first_batch) == BATCH_SIZE
    assert listed == BATCH_SIZE + 1


def test_orphan_candidates_group_by_workspace_and_skip_young_and_foreign_keys() -> None:
    first, second = uuid4(), uuid4()
    first_objects = [_document(first) for _ in range(BATCH_SIZE + 2)]
    second_object = _document(second)
    listing = [
        *first_objects,
        _document(first, modified=CUTOFF),
        StoredObject(key="ws/readme.txt", last_modified=OLD),
        second_object,
    ]

    batches = list(orphan_candidates(listing, CUTOFF))

    assert [(workspace_id, len(batch)) for workspace_id, batch in batches] == [
        (first, BATCH_SIZE),
        (first, 2),
        (second, 1),
    ]
    keys = itertools.chain.from_iterable(batch.values() for _, batch in batches)
    assert list(keys) == [item.key for item in [*first_objects, second_object]]
