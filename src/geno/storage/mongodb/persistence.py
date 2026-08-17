"""MongoDB composition root, initialization, health checks, and statistics."""

from __future__ import annotations

from collections.abc import Callable

from pymongo import IndexModel, MongoClient
from pymongo.database import Database
from pymongo.errors import CollectionInvalid

from geno.config import GenoSettings
from geno.storage.mongodb.codecs import (
    CANDIDATE_UNIT_CODEC,
    EVOLUTION_EDGE_CODEC,
    FAMILY_MEMBER_CODEC,
    GENE_CODEC,
    GENE_FAMILY_CODEC,
    GENE_FEATURE_CODEC,
    GENE_OCCURRENCE_CODEC,
    GENE_STATISTICS_CODEC,
    NORMALIZED_UNIT_CODEC,
    PIPELINE_RUN_CODEC,
    PROCESSING_FAILURE_CODEC,
    REPOSITORY_CODEC,
    SOURCE_FILE_CODEC,
    VERSION_CODEC,
    Document,
    RecordCodec,
)
from geno.storage.mongodb.indexes import COLLECTION_INDEXES, COLLECTION_NAMES
from geno.storage.mongodb.repository import MongoRecordRepository
from geno.storage.mongodb.retry import TransientRetryPolicy
from geno.storage.protocols import (
    DatabaseHealth,
    DatabaseInitializationResult,
    DatabaseOperations,
    DatabaseStatistics,
    PersistenceRepositories,
)


class MongoPersistence(DatabaseOperations, PersistenceRepositories):
    """Own MongoDB client lifecycle and expose typed collection repositories."""

    def __init__(
        self,
        mongodb_uri: str,
        database_name: str,
        *,
        retry_policy: TransientRetryPolicy | None = None,
        server_selection_timeout_ms: int = 3_000,
    ) -> None:
        self._client: MongoClient[Document] = MongoClient(
            mongodb_uri,
            appname="geno",
            connectTimeoutMS=server_selection_timeout_ms,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
            socketTimeoutMS=server_selection_timeout_ms,
            retryReads=True,
            retryWrites=True,
            tz_aware=True,
        )
        self._database: Database[Document] = self._client[database_name]
        self._database_name = database_name
        self._retry_policy = retry_policy or TransientRetryPolicy()

        self.repositories = self._repository("repositories", REPOSITORY_CODEC)
        self.versions = self._repository("versions", VERSION_CODEC)
        self.source_files = self._repository("source_files", SOURCE_FILE_CODEC)
        self.candidate_units = self._repository("candidate_units", CANDIDATE_UNIT_CODEC)
        self.normalized_units = self._repository("normalized_units", NORMALIZED_UNIT_CODEC)
        self.gene_features = self._repository("gene_features", GENE_FEATURE_CODEC)
        self.genes = self._repository("genes", GENE_CODEC)
        self.gene_occurrences = self._repository("gene_occurrences", GENE_OCCURRENCE_CODEC)
        self.gene_statistics = self._repository("gene_statistics", GENE_STATISTICS_CODEC)
        self.evolution_edges = self._repository("evolution_edges", EVOLUTION_EDGE_CODEC)
        self.gene_families = self._repository("gene_families", GENE_FAMILY_CODEC)
        self.family_members = self._repository("family_members", FAMILY_MEMBER_CODEC)
        self.pipeline_runs = self._repository("pipeline_runs", PIPELINE_RUN_CODEC)
        self.processing_failures = self._repository("processing_failures", PROCESSING_FAILURE_CODEC)

    def initialize(self) -> DatabaseInitializationResult:
        existing = set(self._retry_policy.run(self._database.list_collection_names))
        for collection_name in COLLECTION_NAMES:
            if collection_name not in existing:
                self._create_collection(collection_name)

        for collection_name, indexes in COLLECTION_INDEXES.items():
            self._retry_policy.run(self._index_creator(collection_name, indexes))

        index_count = sum(
            len(self._retry_policy.run(self._database[name].index_information))
            for name in COLLECTION_NAMES
        )
        return DatabaseInitializationResult(
            database=self._database_name,
            collection_count=len(COLLECTION_NAMES),
            index_count=index_count,
        )

    def health_check(self) -> DatabaseHealth:
        self._retry_policy.run(lambda: self._client.admin.command("ping"))
        server_info = self._retry_policy.run(self._client.server_info)
        version = server_info.get("version")
        return DatabaseHealth(
            healthy=True,
            database=self._database_name,
            server_version=str(version) if version is not None else None,
        )

    def statistics(self) -> DatabaseStatistics:
        counts = {
            name: self._retry_policy.run(self._document_counter(name)) for name in COLLECTION_NAMES
        }
        return DatabaseStatistics(database=self._database_name, collection_counts=counts)

    def close(self) -> None:
        self._client.close()

    def _repository[RecordT](
        self,
        collection_name: str,
        codec: RecordCodec[RecordT],
    ) -> MongoRecordRepository[RecordT]:
        return MongoRecordRepository(
            self._database[collection_name],
            codec,
            self._retry_policy,
        )

    def _create_collection(self, collection_name: str) -> None:
        def operation() -> None:
            try:
                self._database.create_collection(collection_name)
            except CollectionInvalid:
                # Another initializer may have won the race.
                return

        self._retry_policy.run(operation)

    def _index_creator(
        self,
        collection_name: str,
        indexes: tuple[IndexModel, ...],
    ) -> Callable[[], list[str]]:
        return lambda: self._database[collection_name].create_indexes(list(indexes))

    def _document_counter(self, collection_name: str) -> Callable[[], int]:
        return lambda: self._database[collection_name].count_documents({})


def create_mongo_persistence(settings: GenoSettings) -> MongoPersistence:
    """Create a MongoDB adapter from validated application settings."""
    return MongoPersistence(settings.mongodb_uri, settings.mongodb_database)
