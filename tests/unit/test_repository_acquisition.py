"""Offline tests for repository registration and Git acquisition."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from geno.acquisition import AcquisitionError, GitSubprocessClient, RepositoryAcquisitionService
from geno.acquisition.locator import (
    looks_like_local_path,
    normalize_local_locator,
    normalize_network_locator,
)
from geno.acquisition.models import AcquisitionResult
from geno.domain import ProcessingFailureRecord, RepositoryRecord
from tests.fakes.persistence import FakeRecordRepository

FIXED_TIME = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def test_network_transports_normalize_to_same_repository_identity() -> None:
    https = normalize_network_locator("https://TOKEN@example.com/Group/Sub/Repo.git")
    ssh = normalize_network_locator("git@example.com:group/sub/repo.git")

    assert https.repository_id == ssh.repository_id
    assert https.canonical_locator == "example.com/group/sub/repo"
    assert "TOKEN" not in https.acquisition_locator
    assert https.acquisition_locator == "https://example.com/Group/Sub/Repo.git"


def test_nested_namespaces_support_github_gitlab_gitee_and_generic_hosts() -> None:
    locators = (
        "https://github.com/OpenAI/Geno.git",
        "ssh://git@gitlab.com/team/platform/geno.git",
        "git@gitee.com:team/geno.git",
        "git://git.example.test:9419/group/subgroup/geno.git",
    )

    normalized = tuple(normalize_network_locator(locator) for locator in locators)

    assert [item.name for item in normalized] == ["geno"] * 4
    assert normalized[1].owner == "team/platform"
    assert normalized[3].canonical_locator == "git.example.test:9419/group/subgroup/geno"


def test_local_origin_path_uses_local_identity(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()

    locator = normalize_local_locator(repository, origin="../upstream.git")

    assert locator.source_kind == "local"
    assert locator.canonical_locator.startswith("local:")
    assert looks_like_local_path(r"C:\projects\geno") is True


def test_local_registration_clone_update_refs_and_commits_are_offline(tmp_path: Path) -> None:
    source = _create_local_repository(tmp_path / "source")
    cache = tmp_path / "cache"
    workspace = tmp_path / "workspace"
    repositories = FakeRecordRepository[RepositoryRecord](lambda item: str(item.repository_id))
    failures = FakeRecordRepository[ProcessingFailureRecord](lambda item: item.failure_id)
    service = RepositoryAcquisitionService(
        repositories=repositories,
        processing_failures=failures,
        git=GitSubprocessClient(timeout_seconds=10),
        repository_cache_directory=cache,
        workspace_directory=workspace,
        clock=lambda: FIXED_TIME,
    )

    registered = service.register(str(source))
    paths = service.paths(registered.repository_id)

    assert registered.acquisition_status == "ready"
    assert registered.source_kind == "local"
    assert registered.last_acquired_at == FIXED_TIME
    assert paths.mirror == cache / f"{registered.repository_id}.git"
    assert paths.workspace == workspace / str(registered.repository_id)
    assert paths.mirror.is_dir()
    assert paths.workspace.is_dir()
    assert [(ref.kind, ref.name) for ref in service.refs(registered.repository_id)] == [
        ("branch", "main"),
        ("tag", "v1"),
    ]

    first_commits = service.commits(registered.repository_id)
    assert len(first_commits) == 1
    metadata = service.commit(registered.repository_id, first_commits[0])
    assert metadata.subject == "first"
    assert metadata.parent_object_ids == ()
    assert metadata.author_name == "Geno Fixture"

    _commit(source, "second", "second\n")
    updated = service.update(registered.repository_id)

    assert updated.repository_id == registered.repository_id
    assert len(service.commits(registered.repository_id)) == 2
    assert service.register(str(source)).repository_id == registered.repository_id


def test_acquisition_failure_is_structured_redacted_and_persisted(tmp_path: Path) -> None:
    repositories = FakeRecordRepository[RepositoryRecord](lambda item: str(item.repository_id))
    failures = FakeRecordRepository[ProcessingFailureRecord](lambda item: item.failure_id)
    service = RepositoryAcquisitionService(
        repositories=repositories,
        processing_failures=failures,
        git=FailingGitClient(timeout_seconds=10),
        repository_cache_directory=tmp_path / "cache",
        workspace_directory=tmp_path / "workspace",
        clock=lambda: FIXED_TIME,
    )

    with pytest.raises(AcquisitionError) as captured:
        service.register("https://secret-token@example.com/team/repo.git")

    repository_id = normalize_network_locator("https://example.com/team/repo.git").repository_id
    record = service.show(repository_id)
    failure_page = failures.page()
    assert record.acquisition_status == "failed"
    assert len(failure_page.items) == 1
    failure = failure_page.items[0]
    assert failure.pipeline_run_id is None
    assert failure.target_id == repository_id
    assert "secret-token" not in failure.message
    assert "secret-token" not in str(failure.details)
    assert captured.value.retryable is True


def test_git_subprocess_uses_argument_array_shell_false_and_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["arguments"] = arguments
        observed.update(kwargs)
        return subprocess.CompletedProcess(arguments, 0, stdout="true\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = GitSubprocessClient(timeout_seconds=17)

    assert client.local_repository_root(tmp_path) == tmp_path.resolve()
    assert isinstance(observed["arguments"], list)
    assert observed["shell"] is False
    assert observed["timeout"] == 17
    assert observed["capture_output"] is True


class FailingGitClient(GitSubprocessClient):
    def acquire(
        self,
        repository_id: str,
        source: str,
        *,
        persisted_source: str,
        mirror_path: Path,
        workspace_path: Path,
    ) -> AcquisitionResult:
        raise AcquisitionError(
            code="git_command_failed",
            operation="clone_repository",
            message=f"clone failed for {source}",
            retryable=True,
            stderr=f"fatal: unable to access {source}",
            exit_code=128,
        )


def _create_local_repository(path: Path) -> Path:
    _git(path.parent, "init", "--initial-branch=main", str(path))
    _git(path, "config", "user.name", "Geno Fixture")
    _git(path, "config", "user.email", "fixture@example.test")
    _commit(path, "first", "first\n")
    _git(path, "tag", "v1")
    return path


def _commit(repository: Path, subject: str, content: str) -> None:
    tracked = repository / "tracked.txt"
    tracked.write_text(content, encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "--message", subject)


def _git(cwd: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "GIT_AUTHOR_DATE": "2026-08-06T12:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-08-06T12:00:00+00:00",
        },
    )
    return completed.stdout
