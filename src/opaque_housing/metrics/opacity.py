"""Opacity-tier shares among entity-owned private residential lots. Pure."""

from __future__ import annotations

from typing import Any

import polars as pl

from opaque_housing.metrics.stock import INFORMATIVE_TYPES, private_residential
from opaque_housing.opacity.tiers import OpacityResult
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import ENTITY_OWNED_CLASSES, OpacityTier

_ENTITY = [item.value for item in ENTITY_OWNED_CLASSES]
_TIERS = [item.value for item in OpacityTier]


def attach_opacity(parcels: pl.DataFrame, results: list[OpacityResult]) -> pl.DataFrame:
    if not results:
        return parcels.with_columns(
            pl.lit(None).cast(pl.Utf8).alias("opacity_tier"),
            pl.lit(None).cast(pl.Utf8).alias("opacity_rule_id"),
        )
    table = pl.DataFrame(
        {
            "owner_key": [row.owner_key for row in results],
            "opacity_tier": [row.tier.value for row in results],
            "opacity_rule_id": [row.rule_id for row in results],
        }
    )
    return parcels.join(table, on="owner_key", how="left")


def entity_owned(parcels: pl.DataFrame) -> tuple[pl.DataFrame, FilterCount]:
    rows_in = parcels.height
    entities = parcels.filter(pl.col("owner_class").is_in(_ENTITY))
    return entities, FilterCount("opacity", "entity_owned", rows_in, entities.height)


def _share_block(frame: pl.DataFrame) -> dict[str, Any]:
    units = int(frame["res_units"].sum()) if frame.height else 0
    parcels = frame.height
    by_tier: dict[str, dict[str, Any]] = {}
    for tier in _TIERS:
        part = frame.filter(pl.col("opacity_tier") == tier)
        part_units = int(part["res_units"].sum()) if part.height else 0
        by_tier[tier] = {
            "parcels": part.height,
            "units": part_units,
            "parcel_share": (part.height / parcels) if parcels else None,
            "unit_share": (part_units / units) if units else None,
        }
    return {"parcels": parcels, "units": units, "by_tier": by_tier}


def opacity_headlines(classified: pl.DataFrame) -> dict[str, Any]:
    private, _ = private_residential(classified)
    entities, _ = entity_owned(private)
    informative = entities.filter(pl.col("building_type").is_in(list(INFORMATIVE_TYPES)))
    return {
        "entity_owned": _share_block(entities),
        "sfr_condo": _share_block(informative),
    }


def attach_clusters(parcels: pl.DataFrame, membership: dict[str, str]) -> pl.DataFrame:
    if not membership:
        return parcels.with_columns(pl.lit("").alias("cluster_id"))
    table = pl.DataFrame(
        {
            "owner_key": list(membership.keys()),
            "cluster_id": list(membership.values()),
        }
    )
    return parcels.join(table, on="owner_key", how="left")


def top_cluster_review(
    entities: pl.DataFrame,
    *,
    n: int = 20,
    large_component: int = 200,
) -> list[dict[str, object]]:
    """Summarize the largest clusters. Entity names only; no HPD person names."""
    if entities.is_empty() or "cluster_id" not in entities.columns:
        return []
    work = entities.filter(pl.col("cluster_id").is_not_null() & (pl.col("cluster_id") != ""))
    if work.is_empty():
        return []
    rows: list[dict[str, object]] = []
    for rec in (
        work.group_by("cluster_id")
        .agg(
            pl.len().alias("parcels"),
            pl.col("res_units").sum().alias("units"),
            pl.col("owner_key").n_unique().alias("owners"),
            pl.col("name_normalized").unique().alias("entity_names"),
            pl.col("opacity_tier").eq("O1").sum().alias("o1_parcels"),
        )
        .sort("units", descending=True)
        .head(n)
        .iter_rows(named=True)
    ):
        names = [name for name in rec["entity_names"] if name]
        names = names[:12]
        owners = int(rec["owners"])
        flag = "large_component" if owners >= large_component else ""
        rows.append(
            {
                "cluster_id": rec["cluster_id"],
                "parcels": int(rec["parcels"]),
                "units": int(rec["units"]),
                "owners": owners,
                "o1_parcels": int(rec["o1_parcels"]),
                "entity_names": names,
                "flag": flag,
            }
        )
    return rows


def opacity_by_type(classified: pl.DataFrame) -> pl.DataFrame:
    private, _ = private_residential(classified)
    entities, _ = entity_owned(private)
    if entities.is_empty():
        return pl.DataFrame(
            schema={
                "building_type": pl.Utf8,
                "opacity_tier": pl.Utf8,
                "parcels": pl.UInt32,
                "units": pl.Int64,
                "parcel_share": pl.Float64,
                "unit_share": pl.Float64,
            }
        )
    totals = entities.group_by("building_type").agg(
        pl.len().alias("type_parcels"),
        pl.col("res_units").sum().alias("type_units"),
    )
    counts = entities.group_by(["building_type", "opacity_tier"]).agg(
        pl.len().alias("parcels"),
        pl.col("res_units").sum().alias("units"),
    )
    return (
        counts.join(totals, on="building_type", how="left")
        .with_columns(
            (pl.col("parcels") / pl.col("type_parcels")).alias("parcel_share"),
            (pl.col("units") / pl.col("type_units")).alias("unit_share"),
        )
        .drop(["type_parcels", "type_units"])
        .sort(["building_type", "opacity_tier"])
    )
