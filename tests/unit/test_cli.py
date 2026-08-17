"""Tests for the initial command-line interface."""

import json
from importlib import import_module

import pytest
from typer.testing import CliRunner

from geno import __version__
from geno.acquisition.models import GitReference
from geno.cli.app import app
from geno.domain import RepositoryRecord
from geno.storage import Page
from tests.factories import persistence_records
from tests.fakes.persistence import FakeDatabaseOperations

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "software-gene" in result.stdout
    assert "config" in result.stdout
    assert "repo" in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_config_show_honors_cli_over_environment() -> None:
    # CliRunner uses the process environment, so set it through its invocation API.
    result = runner.invoke(
        app,
        ["--mongodb-database", "from_cli", "config", "show"],
        env={"GENO_MONGODB_DATABASE": "from_environment"},
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["mongodb_database"] == "from_cli"


@pytest.mark.parametrize(
    ("command", "expected_key"),
    [("init", "collection_count"), ("check", "healthy"), ("stats", "total_documents")],
)
def test_database_commands_use_database_operations_fake(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    expected_key: str,
) -> None:
    fake = FakeDatabaseOperations()
    cli_module = import_module("geno.cli.app")
    monkeypatch.setattr(cli_module, "create_mongo_persistence", lambda _: fake)

    result = runner.invoke(app, ["database", command])

    assert result.exit_code == 0
    assert expected_key in json.loads(result.stdout)
    assert fake.closed is True


@pytest.mark.parametrize("command", ["add", "list", "show", "update", "refs"])
def test_repository_commands_use_acquisition_service_fake(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    fake_database = FakeDatabaseOperations()
    fake_service = FakeRepositoryAcquisitionService()
    repository_id = str(fake_service.record.repository_id)
    arguments = {
        "add": ["repo", "add", "/fixture/repository"],
        "list": ["repo", "list"],
        "show": ["repo", "show", repository_id],
        "update": ["repo", "update", repository_id],
        "refs": ["repo", "refs", repository_id],
    }[command]
    cli_module = import_module("geno.cli.app")
    monkeypatch.setattr(cli_module, "create_mongo_persistence", lambda _: fake_database)
    monkeypatch.setattr(cli_module, "_repository_service", lambda _settings, _db: fake_service)

    result = runner.invoke(app, arguments)

    assert result.exit_code == 0, result.stdout
    assert fake_database.closed is True
    assert command in fake_service.calls


class FakeRepositoryAcquisitionService:
    def __init__(self) -> None:
        self.record = persistence_records()[0]
        self.calls: list[str] = []

    def register(self, _locator: str) -> RepositoryRecord:
        self.calls.append("add")
        return self.record

    def list(self, *, after: str | None, limit: int) -> Page[RepositoryRecord]:
        self.calls.append("list")
        return Page(items=(self.record,), next_cursor=None)

    def show(self, _repository_id: str) -> RepositoryRecord:
        self.calls.append("show")
        return self.record

    def update(self, _repository_id: str) -> RepositoryRecord:
        self.calls.append("update")
        return self.record

    def refs(self, _repository_id: str) -> tuple[GitReference, ...]:
        self.calls.append("refs")
        return (
            GitReference(kind="branch", name="main", object_id="a" * 40),
            GitReference(kind="tag", name="v1", object_id="a" * 40),
        )
