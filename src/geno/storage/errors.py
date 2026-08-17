"""Persistence errors that do not expose a database-driver dependency."""


class PersistenceError(RuntimeError):
    """Base error for persistence boundary failures."""


class PersistenceUnavailableError(PersistenceError):
    """Raised after transient database failures exhaust retry attempts."""


class PersistenceDataError(PersistenceError):
    """Raised when stored data violates the explicit serialization contract."""
