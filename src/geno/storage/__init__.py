"""Driver-independent persistence ports and infrastructure factories."""

from geno.storage.errors import PersistenceDataError, PersistenceError, PersistenceUnavailableError
from geno.storage.protocols import (
    BulkUpsertResult,
    DatabaseHealth,
    DatabaseInitializationResult,
    DatabaseOperations,
    DatabaseStatistics,
    Page,
    PersistenceRepositories,
    RecordKey,
    RecordRepository,
    UpsertResult,
)

__all__ = [
    "BulkUpsertResult",
    "DatabaseHealth",
    "DatabaseInitializationResult",
    "DatabaseOperations",
    "DatabaseStatistics",
    "Page",
    "PersistenceDataError",
    "PersistenceError",
    "PersistenceRepositories",
    "PersistenceUnavailableError",
    "RecordKey",
    "RecordRepository",
    "UpsertResult",
]
