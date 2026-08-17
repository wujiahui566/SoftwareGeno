"""Geno software-gene extraction platform."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("software-geno")
except PackageNotFoundError:  # pragma: no cover - supports direct source-tree imports
    __version__ = "0.1.0"

__all__ = ["__version__"]
