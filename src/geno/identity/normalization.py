"""Normalization helpers for repository locators and source paths."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from geno.identity.canonical import normalize_unicode

_SCP_GIT_URL = re.compile(r"^(?:(?P<user>[^@/:]+)@)?(?P<host>[^/:]+):(?P<path>.+)$")
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")
_SUPPORTED_GIT_SCHEMES = frozenset({"git", "http", "https", "ssh"})
_DEFAULT_PORTS = {"git": 9418, "http": 80, "https": 443, "ssh": 22}


@dataclass(frozen=True, slots=True)
class NormalizedGitRepository:
    """Transport-independent Git repository locator components."""

    host: str
    port: int | None
    owner: str
    name: str


def normalize_git_repository(
    git_url: str,
    *,
    owner: str,
    name: str,
) -> NormalizedGitRepository:
    """Normalize a network Git URL and verify its owner/name path."""
    normalized_owner = normalize_repository_owner(owner)
    normalized_name = normalize_repository_name(name)
    host, port, url_path = _parse_git_url(git_url)
    normalized_url_path = _normalize_repository_path(
        url_path,
        percent_decode=True,
        remove_dot_git=True,
    )
    expected_path = f"{normalized_owner}/{normalized_name}"
    if normalized_url_path != expected_path:
        msg = (
            "Git URL path does not match normalized owner/name: "
            f"{normalized_url_path!r} != {expected_path!r}"
        )
        raise ValueError(msg)
    return NormalizedGitRepository(
        host=host,
        port=port,
        owner=normalized_owner,
        name=normalized_name,
    )


def normalize_repository_owner(owner: str) -> str:
    """Normalize an owner or nested namespace using NFC and Unicode case folding."""
    return _normalize_repository_path(owner)


def normalize_repository_name(name: str) -> str:
    """Normalize a repository name using NFC and Unicode case folding."""
    normalized = normalize_unicode(normalize_unicode(name.strip()).casefold())
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if not normalized or "/" in normalized or "\\" in normalized:
        msg = "repository name must be one non-empty path segment"
        raise ValueError(msg)
    if normalized in {".", ".."}:
        msg = "repository name cannot be '.' or '..'"
        raise ValueError(msg)
    return normalized


def normalize_relative_path(path: str) -> str:
    """Normalize a repository-relative Windows or POSIX path to POSIX form."""
    normalized = normalize_unicode(path).replace("\\", "/")
    if normalized.startswith("/") or _WINDOWS_DRIVE.match(normalized):
        msg = "source file path must be repository-relative"
        raise ValueError(msg)

    parts: list[str] = []
    for part in normalized.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            msg = "source file path cannot traverse above the repository root"
            raise ValueError(msg)
        parts.append(part)
    if not parts:
        msg = "source file path cannot be empty"
        raise ValueError(msg)
    return "/".join(parts)


def _parse_git_url(git_url: str) -> tuple[str, int | None, str]:
    normalized_url = normalize_unicode(git_url.strip())
    if "://" not in normalized_url:
        match = _SCP_GIT_URL.fullmatch(normalized_url)
        if match is None:
            msg = f"unsupported Git URL: {git_url!r}"
            raise ValueError(msg)
        return _normalize_host(match.group("host")), None, match.group("path")

    parsed = urlsplit(normalized_url)
    scheme = parsed.scheme.casefold()
    if scheme not in _SUPPORTED_GIT_SCHEMES or parsed.hostname is None:
        msg = f"unsupported Git URL: {git_url!r}"
        raise ValueError(msg)
    if parsed.query or parsed.fragment:
        msg = "Git URL query strings and fragments are not identity-safe"
        raise ValueError(msg)
    try:
        port = parsed.port
    except ValueError as error:
        msg = f"invalid Git URL port: {git_url!r}"
        raise ValueError(msg) from error
    if port == _DEFAULT_PORTS[scheme]:
        port = None
    return _normalize_host(parsed.hostname), port, parsed.path.lstrip("/")


def _normalize_host(host: str) -> str:
    normalized = normalize_unicode(host.strip().rstrip(".")).encode("idna").decode("ascii")
    if not normalized:
        msg = "Git URL host cannot be empty"
        raise ValueError(msg)
    return normalized.casefold()


def _normalize_repository_path(
    path: str,
    *,
    percent_decode: bool = False,
    remove_dot_git: bool = False,
) -> str:
    source = unquote(path) if percent_decode else path
    normalized = normalize_unicode(source.strip()).replace("\\", "/").strip("/")
    if remove_dot_git and normalized.casefold().endswith(".git"):
        normalized = normalized[:-4]
    parts = normalized.split("/")
    if not normalized or any(part in {"", ".", ".."} for part in parts):
        msg = "repository owner/path contains an invalid segment"
        raise ValueError(msg)
    return "/".join(normalize_unicode(part.casefold()) for part in parts)
