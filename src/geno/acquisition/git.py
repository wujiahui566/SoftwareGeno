"""Bounded subprocess adapter for Git repository object acquisition."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Final, Literal, cast

from geno.acquisition.errors import AcquisitionError
from geno.acquisition.models import AcquisitionResult, CommitMetadata, GitReference
from geno.acquisition.security import redact_secrets
from geno.identity import RepositoryId

_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_TRANSIENT_STDERR = re.compile(
    r"(?i)(timed? out|temporary failure|connection (?:reset|refused)|"
    r"could not resolve host|remote end hung up)"
)
_GIT_ENVIRONMENT: Final[dict[str, str]] = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "/bin/false",
    "GIT_CONFIG_NOSYSTEM": "1",
}


class GitSubprocessClient:
    """Run Git with argument arrays, bounded output, and structured errors."""

    def __init__(self, *, timeout_seconds: int = 120, git_executable: str = "git") -> None:
        self._timeout_seconds = timeout_seconds
        self._git_executable = git_executable

    def local_repository_root(self, path: Path) -> Path:
        candidate = path.expanduser().resolve(strict=True)
        bare = self._run(
            ["-C", str(candidate), "rev-parse", "--is-bare-repository"],
            operation="inspect_local_repository",
        ).strip()
        if bare == "true":
            return candidate
        root = self._run(
            ["-C", str(candidate), "rev-parse", "--show-toplevel"],
            operation="inspect_local_repository",
        ).strip()
        return Path(root).resolve(strict=True)

    def remote_origin(self, repository: Path) -> str | None:
        try:
            value = self._run(
                ["-C", str(repository), "remote", "get-url", "origin"],
                operation="read_remote_origin",
            ).strip()
        except AcquisitionError as error:
            if error.exit_code == 2:
                return None
            raise
        return value or None

    def acquire(
        self,
        repository_id: str,
        source: str,
        *,
        persisted_source: str,
        mirror_path: Path,
        workspace_path: Path,
    ) -> AcquisitionResult:
        mirror_path.parent.mkdir(parents=True, exist_ok=True)
        workspace_path.mkdir(parents=True, exist_ok=True)
        created = not mirror_path.exists()
        if created:
            self._clone_mirror(source, persisted_source=persisted_source, mirror_path=mirror_path)
        else:
            self._validate_mirror(mirror_path)
            self._run_git_dir(
                mirror_path,
                ["remote", "set-url", "origin", persisted_source],
                operation="configure_repository_remote",
            )
            self._run_git_dir(
                mirror_path,
                ["remote", "update", "--prune"],
                operation="fetch_repository",
            )

        object_format = self._run_git_dir(
            mirror_path,
            ["rev-parse", "--show-object-format"],
            operation="read_object_format",
        ).strip()
        if object_format not in {"sha1", "sha256"}:
            raise AcquisitionError(
                code="unsupported_git_object_format",
                operation="read_object_format",
                message=f"unsupported Git object format: {object_format!r}",
            )
        head_commit = self._optional_revision(mirror_path, "HEAD")
        default_branch = self._default_branch(mirror_path)
        return AcquisitionResult(
            repository_id=RepositoryId(repository_id),
            mirror_path=mirror_path,
            workspace_path=workspace_path,
            created=created,
            object_format=cast(Literal["sha1", "sha256"], object_format),
            head_commit=head_commit,
            default_branch=default_branch,
        )

    def list_branches(self, mirror_path: Path) -> tuple[GitReference, ...]:
        return self._list_refs(mirror_path, "branch", "refs/heads")

    def list_tags(self, mirror_path: Path) -> tuple[GitReference, ...]:
        return self._list_refs(mirror_path, "tag", "refs/tags")

    def list_commits(self, mirror_path: Path, *, limit: int | None = None) -> tuple[str, ...]:
        if limit is not None and limit < 1:
            raise ValueError("commit limit must be positive")
        arguments = ["rev-list", "--topo-order", "--all"]
        if limit is not None:
            arguments.insert(1, f"--max-count={limit}")
        output = self._run_git_dir(mirror_path, arguments, operation="list_commits")
        return tuple(line for line in output.splitlines() if line)

    def read_commit(self, mirror_path: Path, object_id: str) -> CommitMetadata:
        revision = object_id.casefold()
        if not _OBJECT_ID.fullmatch(revision):
            raise ValueError("commit object ID must be a full SHA-1 or SHA-256 hexadecimal value")
        format_string = "%H%x00%P%x00%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI%x00%s"
        output = self._run_git_dir(
            mirror_path,
            ["show", "-s", f"--format={format_string}", "--end-of-options", revision],
            operation="read_commit_metadata",
        ).rstrip("\n")
        fields = output.split("\0")
        if len(fields) != 9:
            raise AcquisitionError(
                code="invalid_git_output",
                operation="read_commit_metadata",
                message="Git returned malformed commit metadata",
            )
        return CommitMetadata(
            object_id=fields[0],
            parent_object_ids=tuple(fields[1].split()) if fields[1] else (),
            author_name=fields[2],
            author_email=fields[3],
            authored_at=datetime.fromisoformat(fields[4]),
            committer_name=fields[5],
            committer_email=fields[6],
            committed_at=datetime.fromisoformat(fields[7]),
            subject=fields[8],
        )

    def _clone_mirror(self, source: str, *, persisted_source: str, mirror_path: Path) -> None:
        temporary_parent = Path(
            tempfile.mkdtemp(prefix=f".{mirror_path.name}.", dir=mirror_path.parent)
        )
        temporary_mirror = temporary_parent / "mirror.git"
        try:
            clone_arguments = ["clone", "--mirror"]
            if Path(source).is_absolute():
                clone_arguments.append("--no-local")
            clone_arguments.extend(["--", source, str(temporary_mirror)])
            self._run(clone_arguments, operation="clone_repository")
            self._run_git_dir(
                temporary_mirror,
                ["remote", "set-url", "origin", persisted_source],
                operation="sanitize_repository_remote",
            )
            try:
                os.replace(temporary_mirror, mirror_path)
            except OSError:
                if not mirror_path.exists():
                    raise
                self._validate_mirror(mirror_path)
        finally:
            shutil.rmtree(temporary_parent, ignore_errors=True)

    def _validate_mirror(self, mirror_path: Path) -> None:
        if mirror_path.is_symlink() or not mirror_path.is_dir():
            raise AcquisitionError(
                code="invalid_repository_cache",
                operation="validate_repository_cache",
                message=f"repository cache is not a directory: {mirror_path}",
            )
        result = self._run_git_dir(
            mirror_path,
            ["rev-parse", "--is-bare-repository"],
            operation="validate_repository_cache",
        ).strip()
        if result != "true":
            raise AcquisitionError(
                code="invalid_repository_cache",
                operation="validate_repository_cache",
                message=f"repository cache is not a bare Git repository: {mirror_path}",
            )

    def _list_refs(
        self,
        mirror_path: Path,
        kind: Literal["branch", "tag"],
        namespace: str,
    ) -> tuple[GitReference, ...]:
        output = self._run_git_dir(
            mirror_path,
            [
                "for-each-ref",
                "--sort=refname",
                "--format=%(refname)%00%(objectname)%00%(*objectname)",
                namespace,
            ],
            operation=f"list_{kind}s",
        )
        prefix = f"{namespace}/"
        references: list[GitReference] = []
        for line in output.splitlines():
            if not line:
                continue
            refname, object_id, peeled = line.split("\0")
            references.append(
                GitReference(
                    kind=kind,
                    name=refname.removeprefix(prefix),
                    object_id=object_id,
                    peeled_object_id=peeled or None,
                )
            )
        return tuple(references)

    def _optional_revision(self, mirror_path: Path, revision: str) -> str | None:
        try:
            return self._run_git_dir(
                mirror_path,
                ["rev-parse", "--verify", revision],
                operation="resolve_repository_head",
            ).strip()
        except AcquisitionError as error:
            if error.exit_code == 128:
                return None
            raise

    def _default_branch(self, mirror_path: Path) -> str | None:
        try:
            refname = self._run_git_dir(
                mirror_path,
                ["symbolic-ref", "HEAD"],
                operation="read_default_branch",
            ).strip()
        except AcquisitionError as error:
            if error.exit_code == 1:
                return None
            raise
        return refname.removeprefix("refs/heads/")

    def _run_git_dir(self, git_directory: Path, arguments: Sequence[str], *, operation: str) -> str:
        self._validate_cache_path(git_directory)
        return self._run([f"--git-dir={git_directory}", *arguments], operation=operation)

    @staticmethod
    def _validate_cache_path(path: Path) -> None:
        if path.is_symlink():
            raise AcquisitionError(
                code="unsafe_repository_cache",
                operation="validate_repository_cache",
                message=f"repository cache cannot be a symbolic link: {path}",
            )

    def _run(self, arguments: Sequence[str], *, operation: str) -> str:
        environment = os.environ.copy()
        environment.update(_GIT_ENVIRONMENT)
        try:
            completed = subprocess.run(
                [self._git_executable, *arguments],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
                env=environment,
                shell=False,
            )
        except subprocess.TimeoutExpired as error:
            diagnostic = redact_secrets(_timeout_stderr(error))
            raise AcquisitionError(
                code="git_timeout",
                operation=operation,
                message=f"Git operation timed out after {self._timeout_seconds} seconds",
                retryable=True,
                stderr=diagnostic or None,
            ) from None
        except OSError as error:
            raise AcquisitionError(
                code="git_unavailable",
                operation=operation,
                message=redact_secrets(f"unable to execute Git: {error}"),
            ) from error
        if completed.returncode != 0:
            diagnostic = redact_secrets(completed.stderr.strip())
            raise AcquisitionError(
                code="git_command_failed",
                operation=operation,
                message=f"Git {operation.replace('_', ' ')} failed",
                retryable=bool(_TRANSIENT_STDERR.search(diagnostic)),
                stderr=diagnostic or None,
                exit_code=completed.returncode,
            )
        return completed.stdout


def _timeout_stderr(error: subprocess.TimeoutExpired) -> str:
    stderr = error.stderr
    if stderr is None:
        return ""
    return stderr.decode("utf-8", errors="replace")
