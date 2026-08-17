# ADR 0003: MongoDB Persistence Contract

- **Status:** Accepted
- **Date:** 2026-08-06
- **Decision owners:** Geno project maintainers

## Context

Geno requires restartable and idempotent persistence for evidence and derived records while keeping domain and application code independent from MongoDB and PyMongo. The initial adapter must support local batch execution today and deterministic retry/concurrency behavior suitable for later workers.

## Decision

Domain records are immutable Pydantic models. Driver-independent generic repository protocols expose single upsert, bulk upsert, get, and keyset-page operations. Database-operation protocols expose initialization, health, statistics, and close operations. PyMongo is confined to `geno.storage.mongodb`.

Fourteen explicit collections are created: `repositories`, `versions`, `source_files`, `candidate_units`, `normalized_units`, `gene_features`, `genes`, `gene_occurrences`, `gene_statistics`, `evolution_edges`, `gene_families`, `family_members`, `pipeline_runs`, and `processing_failures`.

Each record type has explicit serializer/deserializer functions. Deterministic single-record identifiers mirror to MongoDB `_id`; family members use a deterministic composite storage `_id` and a unique `(family_id, gene_id)` index. Deserialization rejects a storage/domain identity mismatch.

Writes are full-document replacement upserts by deterministic `_id`. Bulk operations are ordered replacement upserts. Repeated writes and retries therefore converge without duplicates. Pagination uses ascending `_id` keysets with an opaque cursor and a maximum page size of 1000.

Initialization safely creates missing collections and named indexes and tolerates another initializer winning the collection-creation race. Required unique and query indexes are versioned in code. Health checks use `ping` plus server metadata; statistics count documents in every declared collection.

PyMongo's retryable read/write support remains enabled. Geno additionally applies a bounded three-attempt exponential-backoff policy to recognized transient failures. Non-transient driver errors and exhausted transient errors are translated into driver-independent persistence exceptions.

## Consequences

- Domain code can be unit-tested using fake protocol implementations without importing PyMongo.
- Deterministic keys and replacement upserts make single and partially retried bulk writes idempotent.
- Full-document replacement gives simple, auditable serialization but requires callers to provide a complete record and use explicit compare-and-set operations for future lease/state transitions.
- Keyset pagination is stable and efficient but supports only deterministic `_id` order through the generic interface; query-specific repositories may add dedicated methods later.
- Standalone MongoDB is sufficient for this adapter. Multi-record workflow consistency still requires reconciliation; a later replica-set decision may add transactions without changing domain identity.

## Compatibility and migration

This is storage schema version 1. No production collections existed before this decision, so no data migration is required. Future field, index, or collection changes require a versioned migration. Identifier semantics remain governed separately by ADR 0002 and are unchanged by this decision.
