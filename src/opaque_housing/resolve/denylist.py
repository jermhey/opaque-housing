"""High-degree address and seed-agent denylist. Pure functions."""

from __future__ import annotations

from collections.abc import Iterable

from opaque_housing.normalize.names import normalize_name

ADDRESS_DEGREE_THRESHOLD = 20
LARGE_COMPONENT_PARCELS = 200


def seed_agent_names(raw_names: Iterable[str]) -> frozenset[str]:
    return frozenset(normalize_name(name) for name in raw_names if name and str(name).strip())


def is_seed_agent(name_normalized: str, seeds: frozenset[str]) -> bool:
    return bool(name_normalized) and name_normalized in seeds


def address_denied(
    address_normalized: str,
    *,
    degree: int,
    agent_name_normalized: str = "",
    seeds: frozenset[str] = frozenset(),
    threshold: int = ADDRESS_DEGREE_THRESHOLD,
) -> bool:
    if not address_normalized:
        return True
    if degree >= threshold:
        return True
    if is_seed_agent(agent_name_normalized, seeds):
        return True
    return False
