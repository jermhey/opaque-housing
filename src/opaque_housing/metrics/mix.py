"""Mix-adjusted NYC vs PHL entity shares. Pure functions on published type tables."""

from __future__ import annotations

from typing import Any

import polars as pl

from opaque_housing.schema import ENTITY_OWNED_CLASSES

_ENTITY = [item.value for item in ENTITY_OWNED_CLASSES]


def building_type_entity_rates(table: pl.DataFrame) -> pl.DataFrame:
    """One row per building type: entity rate and mix weight (parcel and unit)."""
    needed = {
        "building_type",
        "owner_class",
        "class_parcels",
        "class_units",
        "parcels",
        "units",
    }
    missing = needed - set(table.columns)
    if missing:
        raise ValueError(f"stock_by_building_type missing {sorted(missing)}")
    if table.is_empty():
        return pl.DataFrame(
            schema={
                "building_type": pl.Utf8,
                "parcels": pl.Int64,
                "units": pl.Int64,
                "entity_parcels": pl.Int64,
                "entity_units": pl.Int64,
                "parcel_rate": pl.Float64,
                "unit_rate": pl.Float64,
                "parcel_weight": pl.Float64,
                "unit_weight": pl.Float64,
            }
        )
    numeric = table.with_columns(
        pl.col("class_parcels").cast(pl.Int64, strict=False),
        pl.col("class_units").cast(pl.Int64, strict=False),
        pl.col("parcels").cast(pl.Int64, strict=False),
        pl.col("units").cast(pl.Int64, strict=False),
        pl.col("building_type").cast(pl.Utf8),
        pl.col("owner_class").cast(pl.Utf8),
    )
    entity = (
        numeric.filter(pl.col("owner_class").is_in(_ENTITY))
        .group_by("building_type")
        .agg(
            pl.col("class_parcels").sum().alias("entity_parcels"),
            pl.col("class_units").sum().alias("entity_units"),
        )
    )
    totals = numeric.group_by("building_type").agg(
        pl.col("parcels").first(),
        pl.col("units").first(),
    )
    joined = totals.join(entity, on="building_type", how="left").with_columns(
        pl.col("entity_parcels").fill_null(0),
        pl.col("entity_units").fill_null(0),
    )
    parcel_total = int(joined["parcels"].sum())
    unit_total = int(joined["units"].sum())
    return joined.with_columns(
        pl.when(pl.col("parcels") > 0)
        .then(pl.col("entity_parcels") / pl.col("parcels"))
        .otherwise(0.0)
        .alias("parcel_rate"),
        pl.when(pl.col("units") > 0)
        .then(pl.col("entity_units") / pl.col("units"))
        .otherwise(0.0)
        .alias("unit_rate"),
        pl.when(parcel_total > 0)
        .then(pl.col("parcels") / parcel_total)
        .otherwise(0.0)
        .alias("parcel_weight"),
        pl.when(unit_total > 0)
        .then(pl.col("units") / unit_total)
        .otherwise(0.0)
        .alias("unit_weight"),
    ).sort("building_type")


def _rate_weight_maps(
    rates: pl.DataFrame, weight: str
) -> tuple[dict[str, float], dict[str, float]]:
    rate_col = "parcel_rate" if weight == "parcel" else "unit_rate"
    weight_col = "parcel_weight" if weight == "parcel" else "unit_weight"
    rate_map = {
        str(row["building_type"]): float(row[rate_col] or 0.0)
        for row in rates.iter_rows(named=True)
    }
    weight_map = {
        str(row["building_type"]): float(row[weight_col] or 0.0)
        for row in rates.iter_rows(named=True)
    }
    return rate_map, weight_map


def _renorm(weights: dict[str, float], types: list[str]) -> dict[str, float]:
    total = sum(weights.get(item, 0.0) for item in types)
    if total <= 0:
        return {item: 0.0 for item in types}
    return {item: weights.get(item, 0.0) / total for item in types}


def _dot(rates: dict[str, float], weights: dict[str, float], types: list[str]) -> float:
    return sum(rates.get(item, 0.0) * weights.get(item, 0.0) for item in types)


def _observed(rates: dict[str, float], weights: dict[str, float]) -> float:
    return sum(rates[key] * weights[key] for key in rates)


def mix_adjust(
    nyc: pl.DataFrame,
    phl: pl.DataFrame,
    *,
    weight: str = "parcel",
) -> dict[str, Any]:
    """Standardize each metro onto the other's building-type mix.

    ``weight`` is ``parcel`` (the comparable headline) or ``unit``.
    Common-type rows renormalize mix weights to 1. Kitagawa uses Philadelphia
    as the reference mix: NYC − PHL = rate effect + mix effect.
    """
    if weight not in {"parcel", "unit"}:
        raise ValueError("weight must be parcel or unit")
    nyc_rates = building_type_entity_rates(nyc)
    phl_rates = building_type_entity_rates(phl)
    nyc_r, nyc_w = _rate_weight_maps(nyc_rates, weight)
    phl_r, phl_w = _rate_weight_maps(phl_rates, weight)
    nyc_types = list(nyc_r)
    phl_types = list(phl_r)
    common = sorted(set(nyc_types) & set(phl_types))
    nyc_only = sorted(set(nyc_types) - set(phl_types))
    phl_only = sorted(set(phl_types) - set(nyc_types))
    nyc_w_c = _renorm(nyc_w, common)
    phl_w_c = _renorm(phl_w, common)
    nyc_obs = _observed(nyc_r, nyc_w)
    phl_obs = _observed(phl_r, phl_w)
    nyc_obs_common = _dot(nyc_r, nyc_w_c, common)
    phl_obs_common = _dot(phl_r, phl_w_c, common)
    phl_on_nyc = _dot(phl_r, nyc_w_c, common)
    nyc_on_phl = _dot(nyc_r, phl_w_c, common)
    # Rates at NYC mix + composition at PHL rates: identity holds on common types.
    rate_effect = nyc_obs_common - phl_on_nyc
    mix_effect = phl_on_nyc - phl_obs_common
    rows = []
    for btype in sorted(set(nyc_types) | set(phl_types)):
        rows.append(
            {
                "building_type": btype,
                "in_nyc": btype in nyc_r,
                "in_phl": btype in phl_r,
                "nyc_rate": nyc_r.get(btype),
                "phl_rate": phl_r.get(btype),
                "nyc_weight": nyc_w.get(btype),
                "phl_weight": phl_w.get(btype),
            }
        )
    return {
        "weight": weight,
        "entity_classes": list(_ENTITY),
        "common_types": common,
        "nyc_only_types": nyc_only,
        "phl_only_types": phl_only,
        "nyc_observed": nyc_obs,
        "phl_observed": phl_obs,
        "nyc_observed_common": nyc_obs_common,
        "phl_observed_common": phl_obs_common,
        "phl_on_nyc_mix": phl_on_nyc,
        "nyc_on_phl_mix": nyc_on_phl,
        "gap": nyc_obs - phl_obs,
        "gap_common": nyc_obs_common - phl_obs_common,
        "rate_effect": rate_effect,
        "mix_effect": mix_effect,
        "types": rows,
        "caveat": (
            "Common building types only; mix weights renormalized to 1. "
            "NYC co-op buildings have no Philadelphia analogue and are excluded "
            "from the standardized rates. Entity = llc + corp + partnership."
        ),
    }
