"""Stock shares. Pure functions on classified parcel frames."""

from __future__ import annotations

from typing import Any

import polars as pl

from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import (
    ENTITY_OWNED_CLASSES,
    PRIVATE_DENOMINATOR_EXCLUSIONS,
    OwnerClass,
)

INFORMATIVE_TYPES = ("sfr_1_4", "condo_unit")
MIN_PUBLISH_UNITS = 10

_ENTITY = [c.value for c in ENTITY_OWNED_CLASSES]
_EXCLUDED = [c.value for c in PRIVATE_DENOMINATOR_EXCLUSIONS]
_BOROUGH = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
}


def nyc_borough(parcel_id: str) -> str | None:
    if not parcel_id:
        return None
    return _BOROUGH.get(parcel_id[0])


def with_borough(parcels: pl.DataFrame) -> pl.DataFrame:
    return parcels.with_columns(
        pl.col("parcel_id")
        .cast(pl.Utf8)
        .str.slice(0, 1)
        .replace_strict(_BOROUGH, default=None)
        .alias("geo_borough")
    )


def private_residential(parcels: pl.DataFrame) -> tuple[pl.DataFrame, FilterCount]:
    rows_in = parcels.height
    private = parcels.filter(~pl.col("owner_class").is_in(_EXCLUDED))
    count = FilterCount(
        stage="stock_private_denominator",
        rule_id="exclude_public_nonprofit",
        rows_in=rows_in,
        rows_out=private.height,
    )
    return private, count


def _share_table(df: pl.DataFrame, group: list[str]) -> pl.DataFrame:
    if df.is_empty():
        return pl.DataFrame(
            schema={
                **{name: pl.Utf8 for name in group},
                "owner_class": pl.Utf8,
                "class_parcels": pl.UInt32,
                "class_units": pl.Int64,
                "parcels": pl.UInt32,
                "units": pl.Int64,
                "parcel_share": pl.Float64,
                "unit_share": pl.Float64,
            }
        )
    if not group:
        totals = df.select(
            pl.len().alias("parcels"),
            pl.col("res_units").sum().alias("units"),
        )
        by_class = df.group_by("owner_class").agg(
            pl.len().alias("class_parcels"),
            pl.col("res_units").sum().alias("class_units"),
        )
        joined = by_class.join(totals, how="cross")
    else:
        totals = df.group_by(group).agg(
            pl.len().alias("parcels"),
            pl.col("res_units").sum().alias("units"),
        )
        by_class = df.group_by([*group, "owner_class"]).agg(
            pl.len().alias("class_parcels"),
            pl.col("res_units").sum().alias("class_units"),
        )
        joined = by_class.join(totals, on=group)
    return joined.with_columns(
        (pl.col("class_parcels") / pl.col("parcels")).alias("parcel_share"),
        (pl.col("class_units") / pl.col("units")).alias("unit_share"),
    )


def entity_flag(df: pl.DataFrame, include_trust: bool = False) -> pl.DataFrame:
    classes = _ENTITY + ([OwnerClass.TRUST.value] if include_trust else [])
    return df.with_columns(pl.col("owner_class").is_in(classes).alias("is_entity"))


def headline_shares(private: pl.DataFrame) -> dict[str, Any]:
    def _one(frame: pl.DataFrame, include_trust: bool) -> dict[str, float]:
        flagged = entity_flag(frame, include_trust=include_trust)
        parcels = flagged.height
        units = int(flagged["res_units"].sum())
        entity_parcels = flagged.filter(pl.col("is_entity")).height
        entity_units = int(flagged.filter(pl.col("is_entity"))["res_units"].sum())
        return {
            "parcels": parcels,
            "units": units,
            "entity_parcels": entity_parcels,
            "entity_units": entity_units,
            "parcel_share": entity_parcels / parcels if parcels else 0.0,
            "unit_share": entity_units / units if units else 0.0,
        }

    informative = private.filter(pl.col("building_type").is_in(list(INFORMATIVE_TYPES)))
    return {
        "private_all_entity_only": _one(private, False),
        "private_all_entity_plus_trust": _one(private, True),
        "sfr_condo_entity_only": _one(informative, False),
        "sfr_condo_entity_plus_trust": _one(informative, True),
    }


def stock_breakdowns(private: pl.DataFrame) -> dict[str, pl.DataFrame]:
    framed = with_borough(private)
    return {
        "by_class": _share_table(framed, []),
        "by_building_type": _share_table(framed, ["building_type"]),
        "by_borough_type": _share_table(framed, ["geo_borough", "building_type"]),
        "by_nta_type": suppress_small(_share_table(framed, ["geo_neighborhood", "building_type"])),
    }


def suppress_small(table: pl.DataFrame, min_units: int = MIN_PUBLISH_UNITS) -> pl.DataFrame:
    """Null out shares when the cell has fewer than min_units. Rows stay."""
    small = pl.col("units") < min_units
    return table.with_columns(
        pl.when(small).then(None).otherwise(pl.col("parcel_share")).alias("parcel_share"),
        pl.when(small).then(None).otherwise(pl.col("unit_share")).alias("unit_share"),
        small.alias("suppressed"),
    )
