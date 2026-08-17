"""Generic MongoDB implementation of the driver-independent repository protocol."""

from __future__ import annotations

from pymongo import ASCENDING, ReplaceOne
from pymongo.collection import Collection

from geno.storage.mongodb.codecs import Document, RecordCodec
from geno.storage.mongodb.retry import TransientRetryPolicy
from geno.storage.protocols import (
    BulkUpsertResult,
    Page,
    RecordKey,
    RecordRepository,
    UpsertResult,
)


class MongoRecordRepository[RecordT](RecordRepository[RecordT]):
    """Idempotent record persistence using deterministic replacement upserts."""

    def __init__(
        self,
        collection: Collection[Document],
        codec: RecordCodec[RecordT],
        retry_policy: TransientRetryPolicy,
    ) -> None:
        self._collection = collection
        self._codec = codec
        self._retry_policy = retry_policy

    def upsert(self, record: RecordT) -> UpsertResult:
        document = self._codec.serialize(record)

        def operation() -> UpsertResult:
            result = self._collection.replace_one(
                {"_id": document["_id"]},
                document,
                upsert=True,
            )
            return UpsertResult(
                created=result.upserted_id is not None,
                matched_count=result.matched_count,
                modified_count=result.modified_count,
            )

        return self._retry_policy.run(operation)

    def bulk_upsert(self, records: list[RecordT]) -> BulkUpsertResult:
        if not records:
            return BulkUpsertResult(
                requested_count=0,
                created_count=0,
                matched_count=0,
                modified_count=0,
            )
        documents = [self._codec.serialize(record) for record in records]
        operations = [
            ReplaceOne({"_id": document["_id"]}, document, upsert=True) for document in documents
        ]

        def operation() -> BulkUpsertResult:
            result = self._collection.bulk_write(operations, ordered=True)
            return BulkUpsertResult(
                requested_count=len(documents),
                created_count=result.upserted_count,
                matched_count=result.matched_count,
                modified_count=result.modified_count,
            )

        return self._retry_policy.run(operation)

    def get(self, key: RecordKey) -> RecordT | None:
        storage_id = self._codec.storage_id_from_key(key)

        def operation() -> RecordT | None:
            document = self._collection.find_one({"_id": storage_id})
            return None if document is None else self._codec.deserialize(document)

        return self._retry_policy.run(operation)

    def page(self, *, after: str | None = None, limit: int = 100) -> Page[RecordT]:
        if not 1 <= limit <= 1_000:
            msg = "page limit must be between 1 and 1000"
            raise ValueError(msg)
        query: Document = {} if after is None else {"_id": {"$gt": after}}

        def operation() -> Page[RecordT]:
            documents = list(self._collection.find(query).sort("_id", ASCENDING).limit(limit + 1))
            has_more = len(documents) > limit
            selected = documents[:limit]
            next_cursor = str(selected[-1]["_id"]) if has_more and selected else None
            return Page(
                items=tuple(self._codec.deserialize(document) for document in selected),
                next_cursor=next_cursor,
            )

        return self._retry_policy.run(operation)
