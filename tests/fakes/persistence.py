"""In-memory fakes for persistence protocol consumers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from geno.storage import (
    BulkUpsertResult,
    DatabaseHealth,
    DatabaseInitializationResult,
    DatabaseStatistics,
    Page,
    RecordKey,
    UpsertResult,
)


class FakeRecordRepository[RecordT]:
    def __init__(self, key_of: Callable[[RecordT], RecordKey]) -> None:
        self._key_of = key_of
        self._records: dict[RecordKey, RecordT] = {}

    def upsert(self, record: RecordT) -> UpsertResult:
        key = self._key_of(record)
        existing = self._records.get(key)
        self._records[key] = record
        return UpsertResult(
            created=existing is None,
            matched_count=0 if existing is None else 1,
            modified_count=0 if existing == record else int(existing is not None),
        )

    def bulk_upsert(self, records: list[RecordT]) -> BulkUpsertResult:
        results = [self.upsert(record) for record in records]
        return BulkUpsertResult(
            requested_count=len(records),
            created_count=sum(result.created for result in results),
            matched_count=sum(result.matched_count for result in results),
            modified_count=sum(result.modified_count for result in results),
        )

    def get(self, key: RecordKey) -> RecordT | None:
        return self._records.get(key)

    def page(self, *, after: str | None = None, limit: int = 100) -> Page[RecordT]:
        ordered = sorted(self._records.items(), key=lambda item: str(item[0]))
        if after is not None:
            ordered = [item for item in ordered if str(item[0]) > after]
        selected = ordered[:limit]
        has_more = len(ordered) > limit
        return Page(
            items=tuple(record for _, record in selected),
            next_cursor=str(selected[-1][0]) if has_more and selected else None,
        )


@dataclass
class FakeDatabaseOperations:
    database: str = "fake_geno"
    closed: bool = False
    initialized: bool = False
    counts: dict[str, int] = field(default_factory=lambda: {"repositories": 2})

    def initialize(self) -> DatabaseInitializationResult:
        self.initialized = True
        return DatabaseInitializationResult(
            database=self.database,
            collection_count=14,
            index_count=30,
        )

    def health_check(self) -> DatabaseHealth:
        return DatabaseHealth(healthy=True, database=self.database, server_version="8.0.0")

    def statistics(self) -> DatabaseStatistics:
        return DatabaseStatistics(database=self.database, collection_counts=self.counts)

    def close(self) -> None:
        self.closed = True
