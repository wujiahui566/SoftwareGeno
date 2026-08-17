"""Driver-independent persistence protocols and result values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from geno.domain import (
    CandidateUnitRecord,
    EvolutionEdgeRecord,
    FamilyMemberRecord,
    GeneFamilyRecord,
    GeneFeatureRecord,
    GeneOccurrenceRecord,
    GeneRecord,
    GeneStatisticsRecord,
    NormalizedUnitRecord,
    PipelineRunRecord,
    ProcessingFailureRecord,
    RepositoryRecord,
    SourceFileRecord,
    VersionRecord,
)

type RecordKey = str | tuple[str, str]


@dataclass(frozen=True, slots=True)
class UpsertResult:
    created: bool
    matched_count: int
    modified_count: int


@dataclass(frozen=True, slots=True)
class BulkUpsertResult:
    requested_count: int
    created_count: int
    matched_count: int
    modified_count: int


@dataclass(frozen=True, slots=True)
class Page[RecordT]:
    items: tuple[RecordT, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class DatabaseInitializationResult:
    database: str
    collection_count: int
    index_count: int


@dataclass(frozen=True, slots=True)
class DatabaseHealth:
    healthy: bool
    database: str
    server_version: str | None


@dataclass(frozen=True, slots=True)
class DatabaseStatistics:
    database: str
    collection_counts: dict[str, int]

    @property
    def total_documents(self) -> int:
        return sum(self.collection_counts.values())


class RecordRepository[RecordT](Protocol):
    """Persistence operations shared by every record collection."""

    def upsert(self, record: RecordT) -> UpsertResult: ...

    def bulk_upsert(self, records: list[RecordT]) -> BulkUpsertResult: ...

    def get(self, key: RecordKey) -> RecordT | None: ...

    def page(self, *, after: str | None = None, limit: int = 100) -> Page[RecordT]: ...


class DatabaseOperations(Protocol):
    def initialize(self) -> DatabaseInitializationResult: ...

    def health_check(self) -> DatabaseHealth: ...

    def statistics(self) -> DatabaseStatistics: ...

    def close(self) -> None: ...


class PersistenceRepositories(Protocol):
    repositories: RecordRepository[RepositoryRecord]
    versions: RecordRepository[VersionRecord]
    source_files: RecordRepository[SourceFileRecord]
    candidate_units: RecordRepository[CandidateUnitRecord]
    normalized_units: RecordRepository[NormalizedUnitRecord]
    gene_features: RecordRepository[GeneFeatureRecord]
    genes: RecordRepository[GeneRecord]
    gene_occurrences: RecordRepository[GeneOccurrenceRecord]
    gene_statistics: RecordRepository[GeneStatisticsRecord]
    evolution_edges: RecordRepository[EvolutionEdgeRecord]
    gene_families: RecordRepository[GeneFamilyRecord]
    family_members: RecordRepository[FamilyMemberRecord]
    pipeline_runs: RecordRepository[PipelineRunRecord]
    processing_failures: RecordRepository[ProcessingFailureRecord]
