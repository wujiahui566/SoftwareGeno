"""Repository acquisition boundary."""

from geno.acquisition.errors import AcquisitionError, RepositoryNotFoundError
from geno.acquisition.git import GitSubprocessClient
from geno.acquisition.locator import normalize_local_locator, normalize_network_locator
from geno.acquisition.models import (
    AcquisitionResult,
    CommitMetadata,
    GitReference,
    RepositoryLocator,
    RepositoryPaths,
)
from geno.acquisition.protocols import GitRepositoryClient
from geno.acquisition.service import RepositoryAcquisitionService

__all__ = [
    "AcquisitionError",
    "AcquisitionResult",
    "CommitMetadata",
    "GitReference",
    "GitRepositoryClient",
    "GitSubprocessClient",
    "RepositoryAcquisitionService",
    "RepositoryLocator",
    "RepositoryNotFoundError",
    "RepositoryPaths",
    "normalize_local_locator",
    "normalize_network_locator",
]
