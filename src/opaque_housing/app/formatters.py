"""Display helpers for templates and claim cards."""

from __future__ import annotations

from typing import Any


def pct(value: object, digits: int = 1) -> str:
    number = _as_float(value)
    if number is None:
        return "—"
    return f"{number * 100:.{digits}f}%"


def intcomma(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "—"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{int(value):,}"
    if isinstance(value, str):
        try:
            return f"{int(value):,}"
        except ValueError:
            return "—"
    return "—"


def claim_display(card: dict[str, Any]) -> dict[str, Any]:
    return {
        **card,
        "raw_pct": pct(_as_float(card.get("raw"))),
        "corrected_pct": pct(_as_float(card.get("corrected"))),
        "corrected_lo_pct": pct(_as_float(card.get("corrected_lo"))),
        "corrected_hi_pct": pct(_as_float(card.get("corrected_hi"))),
    }


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
