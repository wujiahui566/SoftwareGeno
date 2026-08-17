"""Validated application settings and deterministic source precedence."""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_CONFIG_FILE: Final = Path("configs/default.toml")
CONFIG_FILE_ENVIRONMENT_VARIABLE: Final = "GENO_CONFIG_FILE"


class LogLevel(StrEnum):
    """Supported application log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class GenoSettings(BaseModel):
    """Validated settings used by the Geno application."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = Field(default="geno", min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    workspace_directory: Path = Path(".geno/workspace")
    repository_cache_directory: Path = Path(".geno/repositories")
    temporary_directory: Path = Path(".geno/tmp")
    maximum_worker_count: int = Field(default=4, ge=1)
    git_command_timeout_seconds: int = Field(default=120, ge=1, le=3600)
    log_level: LogLevel = LogLevel.INFO
    fail_fast: bool = False

    @field_validator("mongodb_uri")
    @classmethod
    def validate_mongodb_uri(cls, value: str) -> str:
        """Reject empty and non-MongoDB connection strings early."""
        if not value.startswith(("mongodb://", "mongodb+srv://")):
            msg = "MongoDB URI must start with mongodb:// or mongodb+srv://"
            raise ValueError(msg)
        return value

    @field_validator(
        "workspace_directory",
        "repository_cache_directory",
        "temporary_directory",
        mode="before",
    )
    @classmethod
    def expand_user_directory(cls, value: object) -> object:
        """Expand a leading tilde without making paths host-specific absolute values."""
        if isinstance(value, (str, Path)):
            return Path(value).expanduser()
        return value

    def display_values(self) -> dict[str, Any]:
        """Return JSON-compatible values with MongoDB credentials redacted."""
        values = self.model_dump(mode="json")
        values["mongodb_uri"] = _redact_mongodb_credentials(self.mongodb_uri)
        return values


ENVIRONMENT_FIELDS: Final[dict[str, str]] = {
    "GENO_MONGODB_URI": "mongodb_uri",
    "GENO_MONGODB_DATABASE": "mongodb_database",
    "GENO_WORKSPACE_DIRECTORY": "workspace_directory",
    "GENO_REPOSITORY_CACHE_DIRECTORY": "repository_cache_directory",
    "GENO_TEMPORARY_DIRECTORY": "temporary_directory",
    "GENO_MAXIMUM_WORKER_COUNT": "maximum_worker_count",
    "GENO_GIT_COMMAND_TIMEOUT_SECONDS": "git_command_timeout_seconds",
    "GENO_LOG_LEVEL": "log_level",
    "GENO_FAIL_FAST": "fail_fast",
}


def load_settings(
    *,
    config_file: Path | None = None,
    cli_overrides: Mapping[str, object | None] | None = None,
    environ: Mapping[str, str] | None = None,
) -> GenoSettings:
    """Load settings using CLI > environment > file > default precedence."""
    source_environ = os.environ if environ is None else environ
    selected_file = _select_config_file(config_file, source_environ)

    merged: dict[str, object] = {}
    if selected_file is not None:
        merged.update(_read_config_file(selected_file))

    merged.update(
        {
            field_name: source_environ[environment_name]
            for environment_name, field_name in ENVIRONMENT_FIELDS.items()
            if environment_name in source_environ
        }
    )
    if cli_overrides is not None:
        merged.update({key: value for key, value in cli_overrides.items() if value is not None})

    return GenoSettings.model_validate(merged)


def _select_config_file(config_file: Path | None, environ: Mapping[str, str]) -> Path | None:
    if config_file is not None:
        return config_file
    if configured_path := environ.get(CONFIG_FILE_ENVIRONMENT_VARIABLE):
        return Path(configured_path)
    if DEFAULT_CONFIG_FILE.is_file():
        return DEFAULT_CONFIG_FILE
    return None


def _read_config_file(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as config_stream:
            document = tomllib.load(config_stream)
    except FileNotFoundError:
        msg = f"configuration file does not exist: {path}"
        raise ValueError(msg) from None
    except tomllib.TOMLDecodeError as error:
        msg = f"configuration file is not valid TOML: {path}: {error}"
        raise ValueError(msg) from error

    section = document.get("geno", document)
    if not isinstance(section, dict):
        msg = f"configuration section 'geno' must be a table: {path}"
        raise ValueError(msg)
    return dict(section)


def _redact_mongodb_credentials(uri: str) -> str:
    return re.sub(r"^(mongodb(?:\+srv)?://)([^/@]+)@", r"\1***:***@", uri)
