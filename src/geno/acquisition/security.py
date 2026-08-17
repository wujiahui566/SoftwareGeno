"""Secret redaction for Git locators and bounded diagnostics."""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import SplitResult, urlsplit, urlunsplit

MAX_DIAGNOSTIC_CHARACTERS: Final = 4_000
_TOKEN_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(?i)\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"(?i)\bglpat-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)\b(?:oauth2?|token|access_token|private_token)=([^\s&]+)"),
)


def strip_url_credentials(locator: str) -> str:
    """Remove HTTP(S) credentials while retaining an SSH username."""
    parsed = urlsplit(locator)
    if not parsed.scheme or parsed.hostname is None:
        return locator
    username = parsed.username
    userinfo = f"{username}@" if username and parsed.scheme.casefold() == "ssh" else ""
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    clean = SplitResult(parsed.scheme, f"{userinfo}{host}{port}", parsed.path, "", "")
    return urlunsplit(clean)


def redact_secrets(value: str, *, limit: int = MAX_DIAGNOSTIC_CHARACTERS) -> str:
    """Redact URL userinfo and common access-token forms, then bound output."""
    redacted = re.sub(r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s]+@", r"\1***@", value)
    for pattern in _TOKEN_PATTERNS:
        redacted = pattern.sub(_redacted_token, redacted)
    if len(redacted) > limit:
        return f"{redacted[:limit]}…[truncated]"
    return redacted


def _redacted_token(match: re.Match[str]) -> str:
    token = match.group(0)
    return f"{token.split('=', 1)[0]}=***" if "=" in token else "***"
