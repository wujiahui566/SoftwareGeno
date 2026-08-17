"""Structured, credential-safe repository acquisition errors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AcquisitionError(Exception):
    """A safe error suitable for CLI output and durable diagnostics."""

    code: str
    operation: str
    message: str
    retryable: bool = False
    stderr: str | None = None
    exit_code: int | None = None

    def __str__(self) -> str:
        return self.message


class RepositoryNotFoundError(AcquisitionError):
    """The requested RepositoryID is not registered."""
