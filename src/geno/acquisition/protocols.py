"""Ports used by repository acquisition application services."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from geno.acquisition.models import AcquisitionResult, CommitMetadata, GitReference


class GitRepositoryClient(Protocol):
    def local_repository_root(self, path: Path) -> Path: ...

    def remote_origin(self, repository: Path) -> str | None: ...

    def acquire(
        self,
        repository_id: str,
        source: str,
        *,
        persisted_source: str,
        mirror_path: Path,
        workspace_path: Path,
    ) -> AcquisitionResult: ...

    def list_branches(self, mirror_path: Path) -> tuple[GitReference, ...]: ...

    def list_tags(self, mirror_path: Path) -> tuple[GitReference, ...]: ...

    def list_commits(self, mirror_path: Path, *, limit: int | None = None) -> tuple[str, ...]: ...

    def read_commit(self, mirror_path: Path, object_id: str) -> CommitMetadata: ...
