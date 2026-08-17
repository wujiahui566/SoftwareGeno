"""Canonical serialization used by every deterministic Geno identifier."""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping, Sequence

type CanonicalScalar = str | int | bool | None
type CanonicalValue = CanonicalScalar | list[CanonicalValue] | dict[str, CanonicalValue]


def normalize_unicode(value: str) -> str:
    """Normalize identity-bearing text to Unicode NFC."""
    return unicodedata.normalize("NFC", value)


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    """Serialize the supported identity value subset as canonical UTF-8 JSON.

    Object keys are NFC-normalized and sorted by Unicode code point. Arrays retain their
    order. Callers must sort values whose domain semantics define them as sets.
    """
    normalized = _normalize_value(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _normalize_value(value: object) -> CanonicalValue:
    if value is None or isinstance(value, (bool, int, str)):
        return normalize_unicode(value) if isinstance(value, str) else value
    if isinstance(value, float):
        msg = "floating-point values are not allowed in identifier envelopes"
        raise TypeError(msg)
    if isinstance(value, Mapping):
        normalized: dict[str, CanonicalValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                msg = "identifier envelope keys must be strings"
                raise TypeError(msg)
            normalized_key = normalize_unicode(key)
            if normalized_key in normalized:
                msg = f"duplicate key after Unicode normalization: {normalized_key!r}"
                raise ValueError(msg)
            normalized[normalized_key] = _normalize_value(item)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_value(item) for item in value]

    msg = f"unsupported identifier envelope value: {type(value).__name__}"
    raise TypeError(msg)
