"""O-tier assignment. Pure functions; no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field

from opaque_housing.schema import OpacityTier

OPACITY_VERSION = "2026-09-17.1"


@dataclass(frozen=True)
class OpacityInput:
    owner_key: str
    name_normalized: str
    has_hpd_person: bool
    hpd_person_roles: tuple[str, ...] = ()
    has_dos_chairman_person: bool = False
    has_entity_chain: bool = False
    agent_address_only: bool = False
    dos_matched: bool = False
    address_count: int = 0
    denied_address_count: int = 0


@dataclass(frozen=True)
class OpacityResult:
    owner_key: str
    tier: OpacityTier
    rule_id: str
    evidence: dict[str, object] = field(default_factory=dict)
    rules_version: str = OPACITY_VERSION


def o1_rule(row: OpacityInput) -> str | None:
    if row.has_hpd_person:
        return "T010_hpd_person"
    if row.has_dos_chairman_person:
        return "T020_dos_chairman"
    return None


def assign_tier(row: OpacityInput, cluster_has_o1: bool) -> OpacityResult:
    o1 = o1_rule(row)
    if o1 == "T010_hpd_person":
        tier, rule_id = OpacityTier.O1, o1
    elif o1 == "T020_dos_chairman":
        tier, rule_id = OpacityTier.O1, o1
    elif cluster_has_o1:
        tier, rule_id = OpacityTier.O2, "T030_cluster_o1"
    elif row.has_entity_chain:
        tier, rule_id = OpacityTier.O4, "T040_entity_chain"
    else:
        tier, rule_id = OpacityTier.O3, "T050_no_person"
    return OpacityResult(
        owner_key=row.owner_key,
        tier=tier,
        rule_id=rule_id,
        evidence={
            "name_normalized": row.name_normalized,
            "has_hpd_person": row.has_hpd_person,
            "hpd_person_roles": list(row.hpd_person_roles),
            "has_dos_chairman_person": row.has_dos_chairman_person,
            "has_entity_chain": row.has_entity_chain,
            "agent_address_only": row.agent_address_only,
            "dos_matched": row.dos_matched,
            "address_count": row.address_count,
            "denied_address_count": row.denied_address_count,
            "cluster_has_o1": cluster_has_o1,
        },
    )


def assign_all(
    rows: list[OpacityInput],
    membership: dict[str, str],
) -> list[OpacityResult]:
    o1_clusters: set[str] = set()
    for row in rows:
        if o1_rule(row):
            o1_clusters.add(membership.get(row.owner_key, row.owner_key))
    results: list[OpacityResult] = []
    for row in rows:
        cluster = membership.get(row.owner_key, row.owner_key)
        has_o1 = cluster in o1_clusters and o1_rule(row) is None
        results.append(assign_tier(row, has_o1))
    return results
