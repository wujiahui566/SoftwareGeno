"""Driver-independent values returned by repository acquisition."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from geno.identity import RepositoryId


class AcquisitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RepositoryLocator(AcquisitionModel):
    repository_id: RepositoryId
    source_kind: Literal["network", "local"]
    canonical_locator: str
    acquisition_locator: str
    owner: str
    name: str


class RepositoryPaths(AcquisitionModel):
    mirror: Path
    workspace: Path


class GitReference(AcquisitionModel):
    kind: Literal["branch", "tag"]
    name: str
    object_id: str
    peeled_object_id: str | None = None


class CommitMetadata(AcquisitionModel):
    object_id: str
    parent_object_ids: tuple[str, ...]
    author_name: str
    author_email: str
    authored_at: datetime
    committer_name: str
    committer_email: str
    committed_at: datetime
    subject: str


class AcquisitionResult(AcquisitionModel):
    repository_id: RepositoryId
    mirror_path: Path
    workspace_path: Path
    created: bool
    object_format: Literal["sha1", "sha256"]
    head_commit: str | None
    default_branch: str | None
