"""Pure name normalization. No I/O."""

from __future__ import annotations

import hashlib
import re

_PUNCT = re.compile(r"[^A-Z0-9&/ -]+")
_WS = re.compile(r"\s+")
_SLASH = re.compile(r"\s*/\s*")

# Longer phrases first.
_LLC_PHRASES = (
    (re.compile(r"\bLIMITED LIABILITY COMPANY\b"), "LLC"),
    (re.compile(r"\bLIMITED LIABILITY CO\b"), "LLC"),
    (re.compile(r"\bLTD LIABILITY COMPANY\b"), "LLC"),
    (re.compile(r"\bLTD LIABILITY CO\b"), "LLC"),
    (re.compile(r"\bL\s*L\s*C\b"), "LLC"),
)

_TRUST_PHRASES = (
    (re.compile(r"\bTRUSTEES\b"), "TRUSTEE"),
    (re.compile(r"\bTRUSTEE\b"), "TRUSTEE"),
    (re.compile(r"\bTTEE\b"), "TRUSTEE"),
    (re.compile(r"\bTRST\b"), "TRUST"),
    (re.compile(r"\bLIVING TRUST\b"), "TRUST"),
)

_CORP_PHRASES = (
    (re.compile(r"\bINCORPORATED\b"), "INC"),
    (re.compile(r"\bCORPORATION\b"), "CORP"),
    (re.compile(r"\bP\s*C\b"), "PC"),
)


def normalize_name(raw: str | None) -> str:
    """Uppercase, strip punctuation, collapse space, canonicalize suffixes."""
    if raw is None:
        return ""
    text = raw.upper().replace(".", " ").replace(",", " ")
    text = _PUNCT.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    for pattern, repl in _LLC_PHRASES:
        text = pattern.sub(repl, text)
    for pattern, repl in _TRUST_PHRASES:
        text = pattern.sub(repl, text)
    for pattern, repl in _CORP_PHRASES:
        text = pattern.sub(repl, text)
    return _WS.sub(" ", text).strip()


def owner_key(name_normalized: str) -> str:
    digest = hashlib.sha256(name_normalized.encode("utf-8")).hexdigest()
    return digest[:16]


def split_owner_names(name_normalized: str) -> list[str]:
    """Split only on slash. ``&`` stays one household (ADR 0004)."""
    if not name_normalized:
        return []
    parts = [part.strip() for part in _SLASH.split(name_normalized) if part.strip()]
    return parts or [name_normalized]


def primary_owner_name(raw: str | None) -> str:
    normalized = normalize_name(raw)
    parts = split_owner_names(normalized)
    return parts[0] if parts else ""
