"""Pure address normalization. No I/O."""

from __future__ import annotations

import hashlib
import re

_PUNCT = re.compile(r"[^A-Z0-9/ -]+")
_WS = re.compile(r"\s+")
_CARE_OF = re.compile(r"^(C/O|C O|CARE OF)\b")


def is_care_of(*parts: object) -> bool:
    text = " ".join(str(part).strip() for part in parts if part is not None and str(part).strip())
    if not text:
        return False
    return _CARE_OF.search(text.upper().replace(".", " ")) is not None


def normalize_address(*parts: object) -> str:
    """Uppercase, strip punctuation, drop a leading C/O, collapse space."""
    chunks: list[str] = []
    for part in parts:
        if part is None:
            continue
        text = str(part).strip()
        if text:
            chunks.append(text)
    if not chunks:
        return ""
    text = " ".join(chunks).upper().replace(".", " ").replace(",", " ")
    text = _PUNCT.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    text = _CARE_OF.sub("", text)
    return _WS.sub(" ", text).strip()


def address_key(address_normalized: str) -> str:
    if not address_normalized:
        return ""
    digest = hashlib.sha256(address_normalized.encode("utf-8")).hexdigest()
    return digest[:16]
