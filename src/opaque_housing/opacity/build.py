"""Build per-owner opacity inputs and the link graph. Pure on frames."""

from __future__ import annotations

from collections import defaultdict

import polars as pl

from opaque_housing.adapters.nyc.nys_dos import chairman_is_person, process_name_is_other_entity
from opaque_housing.classify.pipeline import classify_owner
from opaque_housing.opacity.tiers import OpacityInput, OpacityResult, assign_all
from opaque_housing.resolve.cluster import cluster_members
from opaque_housing.resolve.denylist import ADDRESS_DEGREE_THRESHOLD, is_seed_agent
from opaque_housing.resolve.links import (
    address_links,
    concat_links,
    entity_owner_keys,
    key_pair_links,
    person_links,
)
from opaque_housing.schema import ENTITY_OWNED_CLASSES, OwnerClass

_ENTITY = {item.value for item in ENTITY_OWNED_CLASSES}


def attach_parcel_owners(hpd_contacts: pl.DataFrame, parcels: pl.DataFrame) -> pl.DataFrame:
    if hpd_contacts.is_empty() or parcels.is_empty():
        return hpd_contacts.head(0) if "owner_key" in hpd_contacts.columns else hpd_contacts
    owners = parcels.select(["parcel_id", "owner_key", "name_normalized", "owner_class"])
    return hpd_contacts.join(owners, on="parcel_id", how="inner")


def _entity_chain_from_corp_name(corporation_name_normalized: str, owner_name: str) -> bool:
    if not corporation_name_normalized or corporation_name_normalized == owner_name:
        return False
    return classify_owner(corporation_name_normalized).owner_class in {
        OwnerClass.LLC,
        OwnerClass.CORP,
        OwnerClass.PARTNERSHIP,
    }


def build_opacity_inputs(
    parcels: pl.DataFrame,
    hpd_contacts: pl.DataFrame,
    dos_matched: pl.DataFrame,
    *,
    seeds: frozenset[str],
    denied_address_keys: set[str],
) -> list[OpacityInput]:
    owners = entity_owner_keys(parcels)
    hpd_by_owner: dict[str, list[dict[str, object]]] = defaultdict(list)
    if not hpd_contacts.is_empty() and "owner_key" in hpd_contacts.columns:
        for rec in hpd_contacts.iter_rows(named=True):
            hpd_by_owner[str(rec["owner_key"])].append(rec)
    dos_by_owner: dict[str, list[dict[str, object]]] = defaultdict(list)
    if not dos_matched.is_empty() and "owner_key" in dos_matched.columns:
        for rec in dos_matched.iter_rows(named=True):
            dos_by_owner[str(rec["owner_key"])].append(rec)

    rows: list[OpacityInput] = []
    for rec in owners.iter_rows(named=True):
        owner_key = rec["owner_key"]
        name = rec["name_normalized"]
        roles: list[str] = []
        has_person = False
        has_chain = False
        addresses: list[tuple[str, str, str]] = []
        for contact in hpd_by_owner.get(owner_key, []):
            if contact.get("is_o1_person"):
                has_person = True
                role = str(contact.get("type") or "")
                if role and role not in roles:
                    roles.append(role)
            corp = str(contact.get("corporation_name_normalized") or "")
            if _entity_chain_from_corp_name(corp, name):
                has_chain = True
            addr = str(contact.get("address_normalized") or "")
            addr_key = str(contact.get("address_key") or "")
            corp_norm = str(contact.get("corporation_name_normalized") or "")
            addresses.append((addr_key, addr, corp_norm))
        dos_hit = False
        chairman_person = False
        for entity in dos_by_owner.get(owner_key, []):
            dos_hit = True
            chair = str(entity.get("chairman_name_normalized") or "")
            if chairman_is_person(chair):
                chairman_person = True
            process_name = str(entity.get("process_name_normalized") or "")
            if process_name_is_other_entity(process_name, name):
                has_chain = True
            addresses.append(
                (
                    str(entity.get("process_address_key") or ""),
                    str(entity.get("process_address_normalized") or ""),
                    process_name,
                )
            )
        nonempty = [item for item in addresses if item[1]]
        denied = 0
        for addr_key, _addr, agent in nonempty:
            if addr_key in denied_address_keys or is_seed_agent(agent, seeds):
                denied += 1
        agent_only = (not nonempty) or (denied == len(nonempty))
        rows.append(
            OpacityInput(
                owner_key=owner_key,
                name_normalized=name,
                has_hpd_person=has_person,
                hpd_person_roles=tuple(roles),
                has_dos_chairman_person=chairman_person,
                has_entity_chain=has_chain,
                agent_address_only=agent_only,
                dos_matched=dos_hit,
                address_count=len(nonempty),
                denied_address_count=denied,
            )
        )
    return rows


def build_graph(
    parcels: pl.DataFrame,
    hpd_on_parcels: pl.DataFrame,
    dos_matched: pl.DataFrame,
    *,
    seeds: frozenset[str],
    threshold: int = ADDRESS_DEGREE_THRESHOLD,
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, str]]:
    owners = entity_owner_keys(parcels)
    entity_contacts = hpd_on_parcels
    if "owner_class" in hpd_on_parcels.columns:
        entity_contacts = hpd_on_parcels.filter(pl.col("owner_class").is_in(list(_ENTITY)))
    people = person_links(entity_contacts)
    # Address rows still feed the denylist / O3 evidence. They are not cluster
    # edges: mixing them with officer links among all owner classes collapsed
    # tens of thousands of entities into one component.
    _hpd_addr, hpd_denied = address_links(
        entity_contacts,
        owner_col="owner_key",
        address_key_col="address_key",
        address_col="address_normalized",
        agent_name_col=None,
        seeds=seeds,
        link_type="hpd_address",
        threshold=threshold,
    )
    _dos_addr, dos_denied = address_links(
        dos_matched,
        owner_col="owner_key",
        address_key_col="process_address_key",
        address_col="process_address_normalized",
        agent_name_col="process_name_normalized",
        seeds=seeds,
        link_type="dos_process_address",
        threshold=threshold,
    )
    corporate = (
        entity_contacts.filter(pl.col("type") == "CorporateOwner")
        if (not entity_contacts.is_empty() and "type" in entity_contacts.columns)
        else entity_contacts.head(0)
    )
    names = key_pair_links(
        corporate,
        "owner_key",
        "corporation_owner_key",
        link_type="exact_name",
        evidence_col="corporation_name_normalized",
    )
    links = concat_links(people, names)
    denied = (
        pl.concat([hpd_denied, dos_denied], how="diagonal")
        if (hpd_denied.height or dos_denied.height)
        else hpd_denied
    )
    pairs = [
        (rec["owner_key_a"], rec["owner_key_b"])
        for rec in links.iter_rows(named=True)
        if rec["owner_key_a"] and rec["owner_key_b"]
    ]
    extra_nodes = []
    if not corporate.is_empty() and "corporation_owner_key" in corporate.columns:
        extra_nodes.extend([key for key in corporate["corporation_owner_key"].to_list() if key])
    membership = cluster_members(
        [*owners["owner_key"].to_list(), *extra_nodes],
        pairs,
    )
    return links, denied, membership


def run_opacity(
    parcels: pl.DataFrame,
    hpd_on_parcels: pl.DataFrame,
    dos_matched: pl.DataFrame,
    *,
    seeds: frozenset[str],
    threshold: int = ADDRESS_DEGREE_THRESHOLD,
) -> tuple[list[OpacityResult], pl.DataFrame, pl.DataFrame, dict[str, str]]:
    links, denied, membership = build_graph(
        parcels, hpd_on_parcels, dos_matched, seeds=seeds, threshold=threshold
    )
    denied_keys = set(denied["address_key"].to_list()) if denied.height else set()
    inputs = build_opacity_inputs(
        parcels,
        hpd_on_parcels,
        dos_matched,
        seeds=seeds,
        denied_address_keys=denied_keys,
    )
    results = assign_all(inputs, membership)
    return results, links, denied, membership
