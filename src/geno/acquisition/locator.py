"""Parse user-supplied Git locators without retaining credentials."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from geno.acquisition.models import RepositoryLocator
from geno.acquisition.security import strip_url_credentials
from geno.identity import (
    create_local_repository_id,
    create_repository_id,
    normalize_git_repository,
    normalize_repository_name,
    normalize_repository_owner,
)

_SCP_LOCATOR = re.compile(r"^(?:(?P<user>[^@/:]+)@)?(?P<host>[^/:]+):(?P<path>.+)$")
_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_NETWORK_SCHEMES = frozenset({"git", "http", "https", "ssh"})


def looks_like_local_path(value: str) -> bool:
    stripped = value.strip()
    if stripped.startswith((".", "/", "~")) or _WINDOWS_PATH.match(stripped):
        return True
    return "://" not in stripped and _SCP_LOCATOR.fullmatch(stripped) is None


def normalize_network_locator(locator: str) -> RepositoryLocator:
    """Infer owner/name and produce identity and credential-free fetch forms."""
    value = locator.strip()
    if "://" in value:
        parsed = urlsplit(value)
        if parsed.scheme.casefold() not in _NETWORK_SCHEMES or parsed.hostname is None:
            raise ValueError(f"unsupported Git URL: {locator!r}")
        if parsed.query or parsed.fragment:
            raise ValueError("Git URL query strings and fragments are not allowed")
        path = parsed.path
        safe_locator = strip_url_credentials(value)
    else:
        match = _SCP_LOCATOR.fullmatch(value)
        if match is None:
            raise ValueError(f"unsupported Git URL: {locator!r}")
        path = match.group("path")
        safe_locator = value

    owner, name = _owner_and_name(path)
    normalized = normalize_git_repository(value, owner=owner, name=name)
    repository_id = create_repository_id(value, owner=owner, name=name)
    host_port = (
        normalized.host if normalized.port is None else f"{normalized.host}:{normalized.port}"
    )
    canonical = f"{host_port}/{normalized.owner}/{normalized.name}"
    return RepositoryLocator(
        repository_id=repository_id,
        source_kind="network",
        canonical_locator=canonical,
        acquisition_locator=safe_locator,
        owner=normalized.owner,
        name=normalized.name,
    )


def normalize_local_locator(path: Path, *, origin: str | None = None) -> RepositoryLocator:
    """Use origin identity when available, otherwise use local RepositoryID v2."""
    canonical_path = path.resolve(strict=True)
    if origin is not None:
        try:
            network = normalize_network_locator(origin)
        except ValueError:
            # Local/file origins are acquisition details, not portable network identity.
            pass
        else:
            return network.model_copy(
                update={"source_kind": "local", "acquisition_locator": str(canonical_path)}
            )
    name = normalize_repository_name(canonical_path.name.removesuffix(".git"))
    owner = normalize_repository_owner(canonical_path.parent.name or "local")
    return RepositoryLocator(
        repository_id=create_local_repository_id(canonical_path=canonical_path.as_posix()),
        source_kind="local",
        canonical_locator=f"local:{canonical_path.as_posix()}",
        acquisition_locator=str(canonical_path),
        owner=owner,
        name=name,
    )


def _owner_and_name(path: str) -> tuple[str, str]:
    clean = unquote(path).replace("\\", "/").strip("/")
    if clean.casefold().endswith(".git"):
        clean = clean[:-4]
    parts = clean.split("/")
    if len(parts) < 2 or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Git URL must contain an owner/namespace and repository name")
    return "/".join(parts[:-1]), parts[-1]
