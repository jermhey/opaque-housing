"""Stratified gold-set sampling. Pure functions on classified frames."""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence

import polars as pl

DEFAULT_STRATA = ("rule_id", "geo_borough", "building_type")
# Names that are or contain natural persons stay out of the committed gold set.
PRIVATE_GOLD_CLASSES = frozenset({"individual", "trust", "estate", "unknown"})


def _stratum_key(row: dict[str, object], strata: Sequence[str]) -> tuple[object, ...]:
    return tuple(row.get(name) for name in strata)


def _quotas(sizes: dict[tuple[object, ...], int], n: int) -> dict[tuple[object, ...], int]:
    if not sizes or n <= 0:
        return {}
    if len(sizes) >= n:
        ranked = sorted(sizes.items(), key=lambda item: (-item[1], str(item[0])))
        return {key: 1 for key, _ in ranked[:n]}
    total = sum(sizes.values())
    raw = {key: n * size / total for key, size in sizes.items()}
    quotas = {key: max(1, int(share)) for key, share in raw.items()}
    while sum(quotas.values()) > n:
        key = max(quotas, key=lambda item: (quotas[item], str(item)))
        if quotas[key] <= 1:
            break
        quotas[key] -= 1
    while sum(quotas.values()) < n:
        key = max(sizes, key=lambda item: (sizes[item] - quotas[item], str(item)))
        if quotas[key] >= sizes[key]:
            leftover = [item for item, size in sizes.items() if quotas[item] < size]
            if not leftover:
                break
            key = leftover[0]
        quotas[key] += 1
    return quotas


def stratified_owner_sample(
    classified: pl.DataFrame,
    n: int,
    seed: int = 20260916,
    strata: Sequence[str] = DEFAULT_STRATA,
) -> pl.DataFrame:
    """Sample unique normalized names, stratified by rule/borough/type."""
    if classified.is_empty() or n <= 0:
        return classified.head(0)
    work = classified
    if "geo_borough" not in work.columns:
        from opaque_housing.metrics.stock import with_borough

        work = with_borough(work)
    unique = work.unique(subset=["name_normalized", "building_type"], keep="first")
    unique = unique.filter(pl.col("name_normalized") != "")
    rows = list(unique.iter_rows(named=True))
    groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[_stratum_key(row, strata)].append(row)
    sizes = {key: len(items) for key, items in groups.items()}
    quotas = _quotas(sizes, min(n, len(rows)))
    rng = random.Random(seed)
    sampled: list[dict[str, object]] = []
    for key, quota in quotas.items():
        pool = list(groups[key])
        rng.shuffle(pool)
        sampled.extend(pool[:quota])
    return pl.DataFrame(sampled) if sampled else unique.head(0)


def assign_splits(sample: pl.DataFrame, seed: int = 20260916) -> pl.DataFrame:
    """50/50 dev/test within each rule_id so the test split still sees every rule."""
    if sample.is_empty():
        return sample.with_columns(pl.lit("dev").alias("split"))
    rng = random.Random(seed)
    assigned: list[dict[str, object]] = []
    for group in sample.partition_by("rule_id", maintain_order=True):
        rows = list(group.iter_rows(named=True))
        rng.shuffle(rows)
        if len(rows) == 1:
            rows[0]["split"] = "dev" if rng.random() < 0.5 else "test"
        else:
            mid = len(rows) // 2
            for i, row in enumerate(rows):
                row["split"] = "dev" if i < mid else "test"
        assigned.extend(rows)
    return pl.DataFrame(assigned)


def is_private_gold_name(owner_class: str) -> bool:
    return owner_class in PRIVATE_GOLD_CLASSES
