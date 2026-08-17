"""Geno command-line entry point."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Never

import typer
from pydantic import ValidationError

from geno import __version__
from geno.acquisition import AcquisitionError, GitSubprocessClient, RepositoryAcquisitionService
from geno.config import GenoSettings, LogLevel, load_settings
from geno.identity import RepositoryId
from geno.observability import configure_logging
from geno.storage import PersistenceError, PersistenceRepositories
from geno.storage.mongodb import create_mongo_persistence

app = typer.Typer(
    name="geno",
    help="Deterministic software-gene extraction and construction platform.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
config_app = typer.Typer(help="Inspect application configuration.")
database_app = typer.Typer(help="Initialize and inspect MongoDB persistence.")
repository_app = typer.Typer(help="Register and acquire Git repositories.")
app.add_typer(config_app, name="config")
app.add_typer(database_app, name="database")
app.add_typer(repository_app, name="repo")


@app.callback()
def main(
    context: typer.Context,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", help="TOML configuration file."),
    ] = None,
    mongodb_uri: Annotated[
        str | None,
        typer.Option("--mongodb-uri", help="MongoDB connection URI."),
    ] = None,
    mongodb_database: Annotated[
        str | None,
        typer.Option("--mongodb-database", help="MongoDB database name."),
    ] = None,
    workspace_directory: Annotated[
        Path | None,
        typer.Option("--workspace-directory", help="Materialized-version workspace."),
    ] = None,
    repository_cache_directory: Annotated[
        Path | None,
        typer.Option("--repository-cache-directory", help="Repository object cache."),
    ] = None,
    temporary_directory: Annotated[
        Path | None,
        typer.Option("--temporary-directory", help="Temporary working directory."),
    ] = None,
    maximum_worker_count: Annotated[
        int | None,
        typer.Option("--maximum-worker-count", min=1, help="Maximum local workers."),
    ] = None,
    git_command_timeout_seconds: Annotated[
        int | None,
        typer.Option("--git-timeout", min=1, max=3600, help="Git command timeout in seconds."),
    ] = None,
    log_level: Annotated[
        LogLevel | None,
        typer.Option("--log-level", case_sensitive=False, help="Application log level."),
    ] = None,
    fail_fast: Annotated[
        bool | None,
        typer.Option("--fail-fast/--no-fail-fast", help="Stop after the first failure."),
    ] = None,
) -> None:
    """Load configuration shared by all Geno commands."""
    overrides: dict[str, object | None] = {
        "mongodb_uri": mongodb_uri,
        "mongodb_database": mongodb_database,
        "workspace_directory": workspace_directory,
        "repository_cache_directory": repository_cache_directory,
        "temporary_directory": temporary_directory,
        "maximum_worker_count": maximum_worker_count,
        "git_command_timeout_seconds": git_command_timeout_seconds,
        "log_level": log_level,
        "fail_fast": fail_fast,
    }
    try:
        settings = load_settings(config_file=config_file, cli_overrides=overrides)
    except (ValidationError, ValueError) as error:
        typer.echo(f"Configuration error: {error}", err=True)
        raise typer.Exit(code=2) from error

    configure_logging(settings.log_level)
    context.obj = settings


@app.command()
def version() -> None:
    """Print the installed Geno version."""
    typer.echo(__version__)


@config_app.command("show")
def show_config(context: typer.Context) -> None:
    """Print the effective, validated configuration as JSON."""
    settings = _settings_from_context(context)
    typer.echo(json.dumps(settings.display_values(), indent=2, sort_keys=True))


@database_app.command("init")
def initialize_database(context: typer.Context) -> None:
    """Create required MongoDB collections and indexes idempotently."""
    settings = _settings_from_context(context)
    persistence = create_mongo_persistence(settings)
    try:
        result = persistence.initialize()
    except PersistenceError as error:
        typer.echo(f"Database initialization failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    finally:
        persistence.close()
    typer.echo(json.dumps(asdict(result), indent=2, sort_keys=True))


@database_app.command("check")
def check_database(context: typer.Context) -> None:
    """Check MongoDB connectivity and server health."""
    settings = _settings_from_context(context)
    persistence = create_mongo_persistence(settings)
    try:
        result = persistence.health_check()
    except PersistenceError as error:
        typer.echo(f"Database health check failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    finally:
        persistence.close()
    typer.echo(json.dumps(asdict(result), indent=2, sort_keys=True))


@database_app.command("stats")
def database_statistics(context: typer.Context) -> None:
    """Show document counts for every Geno collection."""
    settings = _settings_from_context(context)
    persistence = create_mongo_persistence(settings)
    try:
        result = persistence.statistics()
    except PersistenceError as error:
        typer.echo(f"Database statistics failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    finally:
        persistence.close()
    payload = asdict(result)
    payload["total_documents"] = result.total_documents
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@repository_app.command("add")
def add_repository(context: typer.Context, url_or_path: str) -> None:
    """Register a Git locator and clone its deterministic mirror cache."""
    settings = _settings_from_context(context)
    persistence = create_mongo_persistence(settings)
    try:
        persistence.initialize()
        service = _repository_service(settings, persistence)
        record = service.register(url_or_path)
    except (AcquisitionError, PersistenceError) as error:
        _repository_error("Repository registration failed", error)
    finally:
        persistence.close()
    typer.echo(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True))


@repository_app.command("list")
def list_repositories(
    context: typer.Context,
    after: Annotated[str | None, typer.Option(help="Continue after this RepositoryID.")] = None,
    limit: Annotated[int, typer.Option(min=1, max=1000)] = 100,
) -> None:
    """List registered repositories in deterministic RepositoryID order."""
    settings = _settings_from_context(context)
    persistence = create_mongo_persistence(settings)
    try:
        service = _repository_service(settings, persistence)
        page = service.list(after=after, limit=limit)
    except (AcquisitionError, PersistenceError) as error:
        _repository_error("Repository listing failed", error)
    finally:
        persistence.close()
    payload = {
        "items": [item.model_dump(mode="json") for item in page.items],
        "next_cursor": page.next_cursor,
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@repository_app.command("show")
def show_repository(context: typer.Context, repository_id: str) -> None:
    """Show one registered repository."""
    settings = _settings_from_context(context)
    persistence = create_mongo_persistence(settings)
    try:
        service = _repository_service(settings, persistence)
        record = service.show(RepositoryId(repository_id))
    except (AcquisitionError, PersistenceError) as error:
        _repository_error("Repository lookup failed", error)
    finally:
        persistence.close()
    typer.echo(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True))


@repository_app.command("update")
def update_repository(context: typer.Context, repository_id: str) -> None:
    """Fetch updates into a registered repository mirror."""
    settings = _settings_from_context(context)
    persistence = create_mongo_persistence(settings)
    try:
        service = _repository_service(settings, persistence)
        record = service.update(RepositoryId(repository_id))
    except (AcquisitionError, PersistenceError) as error:
        _repository_error("Repository update failed", error)
    finally:
        persistence.close()
    typer.echo(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True))


@repository_app.command("refs")
def repository_refs(context: typer.Context, repository_id: str) -> None:
    """List branches and tags from the local repository mirror."""
    settings = _settings_from_context(context)
    persistence = create_mongo_persistence(settings)
    try:
        service = _repository_service(settings, persistence)
        references = service.refs(RepositoryId(repository_id))
    except (AcquisitionError, PersistenceError) as error:
        _repository_error("Repository reference listing failed", error)
    finally:
        persistence.close()
    payload = {
        "branches": [ref.model_dump(mode="json") for ref in references if ref.kind == "branch"],
        "tags": [ref.model_dump(mode="json") for ref in references if ref.kind == "tag"],
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _settings_from_context(context: typer.Context) -> GenoSettings:
    return context.ensure_object(GenoSettings)


def _repository_service(
    settings: GenoSettings,
    persistence: PersistenceRepositories,
) -> RepositoryAcquisitionService:
    return RepositoryAcquisitionService(
        repositories=persistence.repositories,
        processing_failures=persistence.processing_failures,
        git=GitSubprocessClient(timeout_seconds=settings.git_command_timeout_seconds),
        repository_cache_directory=settings.repository_cache_directory,
        workspace_directory=settings.workspace_directory,
    )


def _repository_error(prefix: str, error: Exception) -> Never:
    if isinstance(error, AcquisitionError):
        payload = {
            "code": error.code,
            "operation": error.operation,
            "message": error.message,
            "retryable": error.retryable,
            "stderr": error.stderr,
        }
        typer.echo(f"{prefix}: {json.dumps(payload, sort_keys=True)}", err=True)
    else:
        typer.echo(f"{prefix}: {error}", err=True)
    raise typer.Exit(code=1)
