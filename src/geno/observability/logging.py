"""Standard-library logging configuration for Geno."""

from __future__ import annotations

import logging.config

from geno.config.settings import LogLevel


def configure_logging(level: LogLevel | str) -> None:
    """Configure concise UTC-ready application logs on standard error."""
    configured_level = level.value if isinstance(level, LogLevel) else level.upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": configured_level,
                    "stream": "ext://sys.stderr",
                }
            },
            "root": {"handlers": ["console"], "level": configured_level},
        }
    )
