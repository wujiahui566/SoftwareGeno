"""Tests for validated configuration loading."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from geno.config import GenoSettings, LogLevel, load_settings


def test_defaults_are_valid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    settings = load_settings(environ={})

    assert settings == GenoSettings()
    assert settings.log_level is LogLevel.INFO
    assert settings.fail_fast is False


def test_precedence_is_cli_then_environment_then_file_then_defaults(tmp_path: Path) -> None:
    config_file = tmp_path / "geno.toml"
    config_file.write_text(
        """
[geno]
mongodb_database = "from_file"
maximum_worker_count = 2
log_level = "WARNING"
fail_fast = false
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(
        config_file=config_file,
        environ={
            "GENO_MONGODB_DATABASE": "from_environment",
            "GENO_MAXIMUM_WORKER_COUNT": "3",
            "GENO_FAIL_FAST": "true",
        },
        cli_overrides={
            "mongodb_database": "from_cli",
            "maximum_worker_count": 5,
        },
    )

    assert settings.mongodb_database == "from_cli"
    assert settings.maximum_worker_count == 5
    assert settings.fail_fast is True
    assert settings.log_level is LogLevel.WARNING
    assert settings.mongodb_uri == "mongodb://localhost:27017"


def test_environment_can_select_config_file(tmp_path: Path) -> None:
    config_file = tmp_path / "selected.toml"
    config_file.write_text('[geno]\nmongodb_database = "selected"\n', encoding="utf-8")

    settings = load_settings(environ={"GENO_CONFIG_FILE": str(config_file)})

    assert settings.mongodb_database == "selected"


def test_invalid_worker_count_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        load_settings(environ={"GENO_MAXIMUM_WORKER_COUNT": "0"})


def test_display_values_redacts_mongodb_credentials() -> None:
    settings = GenoSettings(mongodb_uri="mongodb://user:secret@localhost:27017")

    assert settings.display_values()["mongodb_uri"] == "mongodb://***:***@localhost:27017"
