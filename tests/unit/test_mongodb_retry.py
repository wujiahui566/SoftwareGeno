"""Tests for bounded transient MongoDB retry handling."""

from __future__ import annotations

import pytest
from pymongo.errors import AutoReconnect, DuplicateKeyError

from geno.storage import PersistenceError, PersistenceUnavailableError
from geno.storage.mongodb import TransientRetryPolicy


def test_transient_error_is_retried_until_success() -> None:
    attempts = 0
    delays: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise AutoReconnect("temporary")
        return "ok"

    policy = TransientRetryPolicy(maximum_attempts=3, sleeper=delays.append)

    assert policy.run(operation) == "ok"
    assert attempts == 3
    assert delays == [0.05, 0.1]


def test_exhausted_transient_error_is_translated() -> None:
    policy = TransientRetryPolicy(maximum_attempts=2, sleeper=lambda _: None)

    with pytest.raises(PersistenceUnavailableError):
        policy.run(lambda: _raise(AutoReconnect("temporary")))


def test_non_transient_driver_error_is_not_retried() -> None:
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise DuplicateKeyError("duplicate")

    policy = TransientRetryPolicy(maximum_attempts=3, sleeper=lambda _: None)

    with pytest.raises(PersistenceError):
        policy.run(operation)
    assert attempts == 1


def _raise(error: Exception) -> None:
    raise error
