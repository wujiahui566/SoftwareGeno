"""Bounded retry handling for transient MongoDB failures."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from pymongo.errors import (
    AutoReconnect,
    ConnectionFailure,
    ExecutionTimeout,
    NetworkTimeout,
    NotPrimaryError,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
    WTimeoutError,
)

from geno.storage.errors import PersistenceError, PersistenceUnavailableError

ResultT = TypeVar("ResultT")

_TRANSIENT_OPERATION_CODES = frozenset(
    {
        6,
        7,
        89,
        91,
        189,
        262,
        9001,
        10107,
        11600,
        11602,
        13435,
        13436,
    }
)
_TRANSIENT_ERROR_TYPES = (
    AutoReconnect,
    ConnectionFailure,
    ExecutionTimeout,
    NetworkTimeout,
    NotPrimaryError,
    ServerSelectionTimeoutError,
    WTimeoutError,
)


@dataclass(frozen=True, slots=True)
class TransientRetryPolicy:
    """Retry transient driver failures with bounded exponential backoff."""

    maximum_attempts: int = 3
    initial_delay_seconds: float = 0.05
    maximum_delay_seconds: float = 0.5
    sleeper: Callable[[float], None] = time.sleep

    def run(self, operation: Callable[[], ResultT]) -> ResultT:
        if self.maximum_attempts < 1:
            msg = "maximum_attempts must be at least one"
            raise ValueError(msg)

        delay = self.initial_delay_seconds
        for attempt in range(1, self.maximum_attempts + 1):
            try:
                return operation()
            except PyMongoError as error:
                if not _is_transient(error):
                    msg = "MongoDB operation failed"
                    raise PersistenceError(msg) from error
                if attempt == self.maximum_attempts:
                    msg = f"MongoDB operation failed after {attempt} transient attempts"
                    raise PersistenceUnavailableError(msg) from error
                self.sleeper(delay)
                delay = min(delay * 2, self.maximum_delay_seconds)
        msg = "unreachable retry state"
        raise AssertionError(msg)


def _is_transient(error: PyMongoError) -> bool:
    if isinstance(error, _TRANSIENT_ERROR_TYPES):
        return True
    if isinstance(error, OperationFailure) and error.code in _TRANSIENT_OPERATION_CODES:
        return True
    return any(
        error.has_error_label(label)
        for label in ("RetryableReadError", "RetryableWriteError", "TransientTransactionError")
    )
