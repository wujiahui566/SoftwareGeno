"""Repository registration and acquisition application service."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import JsonValue

from geno.acquisition.errors import AcquisitionError, RepositoryNotFoundError
from geno.acquisition.locator import (
    looks_like_local_path,
    normalize_local_locator,
    normalize_network_locator,
)
from geno.acquisition.models import (
    CommitMetadata,
    GitReference,
    RepositoryLocator,
    RepositoryPaths,
)
from geno.acquisition.protocols import GitRepositoryClient
from geno.acquisition.security import redact_secrets
from geno.domain import ProcessingFailureRecord, RepositoryRecord
from geno.identity import RepositoryId, canonical_json_bytes
from geno.storage import Page, RecordRepository


class RepositoryAcquisitionService:
    """Coordinate safe Git infrastructure with driver-independent persistence."""

    def __init__(
        self,
        *,
        repositories: RecordRepository[RepositoryRecord],
        processing_failures: RecordRepository[ProcessingFailureRecord],
        git: GitRepositoryClient,
        repository_cache_directory: Path,
        workspace_directory: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repositories = repositories
        self._processing_failures = processing_failures
        self._git = git
        self._repository_cache_directory = repository_cache_directory
        self._workspace_directory = workspace_directory
        self._clock = clock or (lambda: datetime.now(UTC))

    def register(self, url_or_path: str) -> RepositoryRecord:
        """Register and acquire a network URL or local Git repository idempotently."""
        locator, runtime_source = self._resolve_locator(url_or_path)
        existing = self._repositories.get(str(locator.repository_id))
        record = RepositoryRecord(
            repository_id=locator.repository_id,
            canonical_locator=locator.canonical_locator,
            owner=locator.owner,
            name=locator.name,
            source_kind=locator.source_kind,
            acquisition_locator=locator.acquisition_locator,
            acquisition_status="registered",
            default_branch=existing.default_branch if existing else None,
            last_acquired_at=existing.last_acquired_at if existing else None,
            metadata=existing.metadata if existing else {},
        )
        self._repositories.upsert(record)
        return self._acquire(record, runtime_source=runtime_source)

    def update(self, repository_id: RepositoryId) -> RepositoryRecord:
        """Fetch a previously registered repository and update observed metadata."""
        record = self.show(repository_id)
        if record.acquisition_locator is None:
            raise AcquisitionError(
                code="missing_acquisition_locator",
                operation="fetch_repository",
                message=f"repository has no acquisition locator: {repository_id}",
            )
        return self._acquire(record, runtime_source=record.acquisition_locator)

    def list(self, *, after: str | None = None, limit: int = 100) -> Page[RepositoryRecord]:
        return self._repositories.page(after=after, limit=limit)

    def show(self, repository_id: RepositoryId) -> RepositoryRecord:
        record = self._repositories.get(str(repository_id))
        if record is None:
            raise RepositoryNotFoundError(
                code="repository_not_found",
                operation="read_repository",
                message=f"repository is not registered: {repository_id}",
            )
        return record

    def paths(self, repository_id: RepositoryId) -> RepositoryPaths:
        return RepositoryPaths(
            mirror=self._repository_cache_directory / f"{repository_id}.git",
            workspace=self._workspace_directory / str(repository_id),
        )

    def refs(self, repository_id: RepositoryId) -> tuple[GitReference, ...]:
        paths = self._ready_paths(repository_id)
        return (*self._git.list_branches(paths.mirror), *self._git.list_tags(paths.mirror))

    def commits(self, repository_id: RepositoryId, *, limit: int | None = None) -> tuple[str, ...]:
        paths = self._ready_paths(repository_id)
        return self._git.list_commits(paths.mirror, limit=limit)

    def commit(self, repository_id: RepositoryId, object_id: str) -> CommitMetadata:
        paths = self._ready_paths(repository_id)
        return self._git.read_commit(paths.mirror, object_id)

    def _resolve_locator(self, value: str) -> tuple[RepositoryLocator, str]:
        try:
            if looks_like_local_path(value):
                root = self._git.local_repository_root(Path(value))
                origin = self._git.remote_origin(root)
                return normalize_local_locator(root, origin=origin), str(root)
            return normalize_network_locator(value), value.strip()
        except AcquisitionError:
            raise
        except (OSError, ValueError) as error:
            raise AcquisitionError(
                code="invalid_repository_locator",
                operation="register_repository",
                message=redact_secrets(str(error)),
            ) from error

    def _acquire(self, record: RepositoryRecord, *, runtime_source: str) -> RepositoryRecord:
        paths = self.paths(record.repository_id)
        try:
            result = self._git.acquire(
                str(record.repository_id),
                runtime_source,
                persisted_source=record.acquisition_locator or runtime_source,
                mirror_path=paths.mirror,
                workspace_path=paths.workspace,
            )
        except AcquisitionError as error:
            safe_error = AcquisitionError(
                code=error.code,
                operation=error.operation,
                message=redact_secrets(error.message),
                retryable=error.retryable,
                stderr=redact_secrets(error.stderr) if error.stderr else None,
                exit_code=error.exit_code,
            )
            failed = record.model_copy(update={"acquisition_status": "failed"})
            self._repositories.upsert(failed)
            self._processing_failures.upsert(self._failure(record.repository_id, safe_error))
            raise safe_error from error
        completed = record.model_copy(
            update={
                "default_branch": result.default_branch,
                "acquisition_status": "ready",
                "last_acquired_at": self._clock(),
                "metadata": {
                    **record.metadata,
                    "git_object_format": result.object_format,
                    "head_commit": result.head_commit,
                },
            }
        )
        self._repositories.upsert(completed)
        return completed

    def _ready_paths(self, repository_id: RepositoryId) -> RepositoryPaths:
        record = self.show(repository_id)
        if record.acquisition_status != "ready":
            raise AcquisitionError(
                code="repository_not_acquired",
                operation="read_repository_cache",
                message=f"repository has not been acquired successfully: {repository_id}",
            )
        return self.paths(repository_id)

    def _failure(
        self,
        repository_id: RepositoryId,
        error: AcquisitionError,
    ) -> ProcessingFailureRecord:
        diagnostic = {
            "repository_id": repository_id,
            "stage": "repository_acquisition",
            "operation": error.operation,
            "code": error.code,
            "stderr": error.stderr,
        }
        digest = hashlib.sha256(canonical_json_bytes(diagnostic)).hexdigest()
        details: dict[str, JsonValue] = {
            "operation": error.operation,
            "stderr": error.stderr,
            "exit_code": error.exit_code,
        }
        return ProcessingFailureRecord(
            failure_id=f"failure_{digest}",
            stage="repository_acquisition",
            target_kind="repository",
            target_id=str(repository_id),
            error_code=error.code,
            message=redact_secrets(error.message),
            retryable=error.retryable,
            attempt=1,
            occurred_at=self._clock(),
            details=details,
        )
