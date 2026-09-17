"""Attach rule classifications to a parcel frame. Pure besides the input frame."""

from __future__ import annotations

import polars as pl

from opaque_housing.classify.pipeline import classify_owner
from opaque_housing.schema import BuildingType


def classify_parcel_frame(parcels: pl.DataFrame) -> pl.DataFrame:
    """Join owner_class / rule_id onto each parcel via unique name × building type."""
    if parcels.is_empty():
        return parcels.with_columns(
            pl.lit("").alias("owner_key"),
            pl.lit("").alias("name_normalized"),
            pl.lit("unknown").alias("owner_class"),
            pl.lit("rule").alias("class_source"),
            pl.lit("R001_blank").alias("rule_id"),
        )

    work = parcels.with_columns(
        pl.col("owner_name_raw").cast(pl.Utf8).fill_null("").alias("owner_name_raw"),
        pl.col("building_type").cast(pl.Utf8).fill_null("").alias("building_type"),
    )
    keys = work.select(["owner_name_raw", "building_type"]).unique()
    rows: list[dict[str, str]] = []
    for rec in keys.iter_rows(named=True):
        raw = rec["owner_name_raw"]
        bt_raw = rec["building_type"]
        building_type = BuildingType(bt_raw) if bt_raw else None
        owner = classify_owner(raw, building_type)
        rows.append(
            {
                "owner_name_raw": raw,
                "building_type": bt_raw,
                "owner_key": owner.owner_key,
                "name_normalized": owner.name_normalized,
                "owner_class": owner.owner_class.value,
                "class_source": owner.class_source.value,
                "rule_id": owner.rule_id or "",
            }
        )
    classified = pl.DataFrame(rows)
    return work.join(classified, on=["owner_name_raw", "building_type"], how="left")
