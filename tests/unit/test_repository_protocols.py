"""Unit tests use fake repositories rather than importing MongoDB infrastructure."""

from __future__ import annotations

from geno.domain import RepositoryRecord
from geno.identity import RepositoryId
from geno.storage import RecordRepository
from tests.factories import persistence_records
from tests.fakes.persistence import FakeRecordRepository


def test_protocol_consumer_gets_idempotent_fake_upserts() -> None:
    record = persistence_records()[0]
    repository: RecordRepository[RepositoryRecord] = FakeRecordRepository(
        lambda item: str(item.repository_id)
    )

    first = repository.upsert(record)
    second = repository.upsert(record)

    assert first.created is True
    assert second.created is False
    assert second.modified_count == 0
    assert repository.get(str(record.repository_id)) == record


def test_fake_repository_supports_bulk_updates_and_keyset_pages() -> None:
    base = persistence_records()[0]
    records = [
        base.model_copy(
            update={
                "repository_id": RepositoryId(f"repo_{index:064x}"),
                "name": f"geno-{index}",
            }
        )
        for index in range(3)
    ]
    repository: RecordRepository[RepositoryRecord] = FakeRecordRepository(
        lambda item: str(item.repository_id)
    )

    result = repository.bulk_upsert(records)
    first_page = repository.page(limit=2)
    second_page = repository.page(after=first_page.next_cursor, limit=2)

    assert result.created_count == 3
    assert len(first_page.items) == 2
    assert first_page.next_cursor is not None
    assert len(second_page.items) == 1
    assert second_page.next_cursor is None
