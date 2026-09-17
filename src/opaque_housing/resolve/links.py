"""Build owner-to-owner links. Pure functions on frames."""

from __future__ import annotations

from collections import defaultdict

import polars as pl

from opaque_housing.resolve.denylist import ADDRESS_DEGREE_THRESHOLD, is_seed_agent
from opaque_housing.schema import ENTITY_OWNED_CLASSES

_ENTITY = {item.value for item in ENTITY_OWNED_CLASSES}


def entity_owner_keys(parcels: pl.DataFrame) -> pl.DataFrame:
    if parcels.is_empty():
        return pl.DataFrame(
            schema={
                "owner_key": pl.Utf8,
                "name_normalized": pl.Utf8,
                "owner_class": pl.Utf8,
            }
        )
    return (
        parcels.filter(pl.col("owner_class").is_in(list(_ENTITY)))
        .select(["owner_key", "name_normalized", "owner_class"])
        .unique()
        .filter(pl.col("owner_key") != "")
    )


def _star_pairs(owners: list[str]) -> list[tuple[str, str]]:
    unique = sorted({owner for owner in owners if owner})
    if len(unique) < 2:
        return []
    hub = unique[0]
    return [(hub, other) if hub <= other else (other, hub) for other in unique[1:]]


def person_links(hpd_contacts: pl.DataFrame) -> pl.DataFrame:
    """Star-links among entity owners who share an O1 person_key."""
    if hpd_contacts.is_empty() or "is_o1_person" not in hpd_contacts.columns:
        return _empty_links()
    people = hpd_contacts.filter(pl.col("is_o1_person") & (pl.col("person_key") != ""))
    if "owner_key" not in people.columns:
        return _empty_links()
    grouped: dict[str, list[str]] = defaultdict(list)
    evidence: dict[str, str] = {}
    for rec in people.select(["person_key", "owner_key", "person_name_normalized"]).iter_rows(
        named=True
    ):
        grouped[rec["person_key"]].append(rec["owner_key"])
        evidence[rec["person_key"]] = rec.get("person_name_normalized") or rec["person_key"]
    rows: list[dict[str, str]] = []
    for person_key, owners in grouped.items():
        for left, right in _star_pairs(owners):
            rows.append(
                {
                    "owner_key_a": left,
                    "owner_key_b": right,
                    "link_type": "hpd_person",
                    "evidence_ref": evidence.get(person_key, person_key),
                }
            )
    return pl.DataFrame(rows) if rows else _empty_links()


def address_links(
    rows: pl.DataFrame,
    *,
    owner_col: str,
    address_key_col: str,
    address_col: str,
    agent_name_col: str | None,
    seeds: frozenset[str],
    link_type: str,
    threshold: int = ADDRESS_DEGREE_THRESHOLD,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return (links, denied_addresses). Degree is distinct owner_keys."""
    if rows.is_empty() or address_key_col not in rows.columns:
        return _empty_links(), _empty_denied()
    work = rows.filter(pl.col(address_key_col) != "")
    if work.is_empty():
        return _empty_links(), _empty_denied()
    by_addr: dict[str, set[str]] = defaultdict(set)
    meta: dict[str, dict[str, str]] = {}
    for rec in work.iter_rows(named=True):
        key = rec[address_key_col]
        owner = rec.get(owner_col) or ""
        if not owner:
            continue
        by_addr[key].add(owner)
        agent = rec.get(agent_name_col, "") if agent_name_col else ""
        meta[key] = {
            "address_key": key,
            "address_normalized": rec.get(address_col) or "",
            "agent_name_normalized": agent or "",
        }
    link_rows: list[dict[str, str]] = []
    denied_rows: list[dict[str, object]] = []
    for key, owners in by_addr.items():
        info = meta[key]
        degree = len(owners)
        denied = (not info["address_normalized"]) or degree >= threshold
        if not denied and info["agent_name_normalized"]:
            denied = is_seed_agent(info["agent_name_normalized"], seeds)
        if denied:
            denied_rows.append(
                {
                    "address_key": key,
                    "address_normalized": info["address_normalized"],
                    "degree": degree,
                    "reason": "seed_agent" if degree < threshold else "high_degree",
                }
            )
            continue
        for left, right in _star_pairs(list(owners)):
            link_rows.append(
                {
                    "owner_key_a": left,
                    "owner_key_b": right,
                    "link_type": link_type,
                    "evidence_ref": info["address_normalized"],
                }
            )
    links = pl.DataFrame(link_rows) if link_rows else _empty_links()
    denied = pl.DataFrame(denied_rows) if denied_rows else _empty_denied()
    return links, denied


def key_pair_links(
    frame: pl.DataFrame,
    left_col: str,
    right_col: str,
    *,
    link_type: str,
    evidence_col: str | None = None,
) -> pl.DataFrame:
    """Link two key columns on the same row when they differ and are non-empty."""
    if frame.is_empty() or left_col not in frame.columns or right_col not in frame.columns:
        return _empty_links()
    rows: list[dict[str, str]] = []
    cols = [left_col, right_col] + ([evidence_col] if evidence_col else [])
    for rec in frame.select(cols).iter_rows(named=True):
        left = rec.get(left_col) or ""
        right = rec.get(right_col) or ""
        if not left or not right or left == right:
            continue
        a, b = (left, right) if left <= right else (right, left)
        rows.append(
            {
                "owner_key_a": a,
                "owner_key_b": b,
                "link_type": link_type,
                "evidence_ref": str(rec.get(evidence_col) or right) if evidence_col else right,
            }
        )
    return pl.DataFrame(rows).unique() if rows else _empty_links()


def concat_links(*frames: pl.DataFrame) -> pl.DataFrame:
    nonempty = [frame for frame in frames if frame.height]
    if not nonempty:
        return _empty_links()
    return pl.concat(nonempty, how="diagonal").unique(
        subset=["owner_key_a", "owner_key_b", "link_type"]
    )


def _empty_links() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "owner_key_a": pl.Utf8,
            "owner_key_b": pl.Utf8,
            "link_type": pl.Utf8,
            "evidence_ref": pl.Utf8,
        }
    )


def _empty_denied() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "address_key": pl.Utf8,
            "address_normalized": pl.Utf8,
            "degree": pl.Int64,
            "reason": pl.Utf8,
        }
    )
