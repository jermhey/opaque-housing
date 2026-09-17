"""Reconstructed historical stock and PLUTO consistency. Pure functions."""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl

from opaque_housing.metrics.flow import WINDOW_END, WINDOW_START
from opaque_housing.metrics.stock import (
    INFORMATIVE_TYPES,
    headline_shares,
    private_residential,
    with_borough,
)
from opaque_housing.schema import ENTITY_OWNED_CLASSES

_ENTITY = [item.value for item in ENTITY_OWNED_CLASSES]


def owner_as_of(parcel_sales: pl.DataFrame, as_of: date) -> pl.DataFrame:
    """Latest sale deed per parcel on or before ``as_of``."""
    eligible = parcel_sales.filter(pl.col("recorded_date").is_not_null()).filter(
        pl.col("recorded_date") <= as_of
    )
    if eligible.is_empty():
        return eligible
    return (
        eligible.sort(["parcel_id", "recorded_date", "doc_id"])
        .group_by("parcel_id", maintain_order=True)
        .last()
    )


def year_end_dates(start: int = WINDOW_START, end: int = WINDOW_END) -> list[date]:
    return [date(year, 12, 31) for year in range(start, end + 1)]


def historical_stock_table(
    parcel_sales: pl.DataFrame,
    parcels: pl.DataFrame,
    as_of_dates: list[date] | None = None,
) -> pl.DataFrame:
    """Entity shares of reconstructed owners at each year-end.

    Building type and units come from the current PLUTO snapshot (not historical
    use). Parcels with no sale on or before the date are out of the universe.
    """
    attrs = parcels.select(
        "parcel_id",
        "building_type",
        "res_units",
        "geo_neighborhood",
        "geo_tract",
    )
    rows: list[dict[str, Any]] = []
    for as_of in as_of_dates or year_end_dates():
        owned = owner_as_of(parcel_sales, as_of)
        if owned.is_empty():
            rows.append(
                {
                    "as_of": as_of.isoformat(),
                    "year": as_of.year,
                    "parcels": 0,
                    "units": 0,
                    "entity_parcels": 0,
                    "entity_units": 0,
                    "parcel_share": 0.0,
                    "unit_share": 0.0,
                    "sfr_condo_parcels": 0,
                    "sfr_condo_units": 0,
                    "sfr_condo_entity_unit_share": 0.0,
                    "coverage_parcels": 0.0,
                }
            )
            continue
        framed = owned.join(attrs, on="parcel_id", how="left").filter(
            pl.col("building_type").is_not_null()
        )
        if "owner_class" in framed.columns:
            framed = framed.drop("owner_class")
        framed = framed.rename({"buyer_class": "owner_class"})
        private, _ = private_residential(framed)
        headlines = headline_shares(private) if private.height else None
        informative = (
            private.filter(pl.col("building_type").is_in(list(INFORMATIVE_TYPES)))
            if private.height
            else private
        )
        entity_info = informative.filter(pl.col("owner_class").is_in(_ENTITY))
        info_units = int(informative["res_units"].sum()) if informative.height else 0
        info_entity = int(entity_info["res_units"].sum()) if entity_info.height else 0
        city = headlines["private_all_entity_only"] if headlines else None
        rows.append(
            {
                "as_of": as_of.isoformat(),
                "year": as_of.year,
                "parcels": 0 if city is None else city["parcels"],
                "units": 0 if city is None else city["units"],
                "entity_parcels": 0 if city is None else city["entity_parcels"],
                "entity_units": 0 if city is None else city["entity_units"],
                "parcel_share": 0.0 if city is None else city["parcel_share"],
                "unit_share": 0.0 if city is None else city["unit_share"],
                "sfr_condo_parcels": informative.height,
                "sfr_condo_units": info_units,
                "sfr_condo_entity_unit_share": (info_entity / info_units if info_units else 0.0),
                "coverage_parcels": (framed.height / parcels.height if parcels.height else 0.0),
            }
        )
    return pl.DataFrame(rows)


def consistency_check(
    parcel_sales: pl.DataFrame,
    parcels: pl.DataFrame,
    as_of: date,
) -> dict[str, Any]:
    """Reconstructed current owner class vs PLUTO owner class."""
    reconstructed = owner_as_of(parcel_sales, as_of)
    compared = parcels.join(reconstructed, on="parcel_id", how="inner")
    if compared.is_empty():
        return {
            "as_of": as_of.isoformat(),
            "n_pluto": parcels.height,
            "n_reconstructed": reconstructed.height,
            "n_compared": 0,
            "n_pluto_without_deed": parcels.height,
            "n_deed_without_pluto": reconstructed.height,
            "class_agree": 0,
            "entity_agree": 0,
            "class_agree_rate": None,
            "entity_agree_rate": None,
            "by_building_type": [],
        }
    compared = compared.with_columns(
        (pl.col("owner_class") == pl.col("buyer_class")).alias("class_agree"),
        (pl.col("owner_class").is_in(_ENTITY) == pl.col("buyer_class").is_in(_ENTITY)).alias(
            "entity_agree"
        ),
    )
    compared = with_borough(compared)
    by_type = (
        compared.group_by("building_type")
        .agg(
            pl.len().alias("n"),
            pl.col("class_agree").sum().alias("class_agree"),
            pl.col("entity_agree").sum().alias("entity_agree"),
        )
        .with_columns(
            (pl.col("class_agree") / pl.col("n")).alias("class_agree_rate"),
            (pl.col("entity_agree") / pl.col("n")).alias("entity_agree_rate"),
        )
    )
    n = compared.height
    return {
        "as_of": as_of.isoformat(),
        "n_pluto": parcels.height,
        "n_reconstructed": reconstructed.height,
        "n_compared": n,
        "n_pluto_without_deed": parcels.height - n,
        "n_deed_without_pluto": reconstructed.height - n,
        "class_agree": int(compared["class_agree"].sum()),
        "entity_agree": int(compared["entity_agree"].sum()),
        "class_agree_rate": float(compared["class_agree"].sum()) / n,
        "entity_agree_rate": float(compared["entity_agree"].sum()) / n,
        "by_building_type": by_type.to_dicts(),
    }
