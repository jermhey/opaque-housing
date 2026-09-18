"""Mix-adjusted pairwise entity shares. Pure functions on published type tables."""

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
    reference: pl.DataFrame,
    other: pl.DataFrame,
    *,
    weight: str = "parcel",
    reference_id: str = "nyc",
    other_id: str = "phl",
) -> dict[str, Any]:
    """Standardize each metro onto the other's building-type mix.

    ``weight`` is ``parcel`` (the comparable headline) or ``unit``.
    Common-type rows renormalize mix weights to 1. Kitagawa uses ``other`` as
    the reference mix: reference − other = rate effect + mix effect.
    """
    if weight not in {"parcel", "unit"}:
        raise ValueError("weight must be parcel or unit")
    ref_rates = building_type_entity_rates(reference)
    oth_rates = building_type_entity_rates(other)
    ref_r, ref_w = _rate_weight_maps(ref_rates, weight)
    oth_r, oth_w = _rate_weight_maps(oth_rates, weight)
    ref_types = list(ref_r)
    oth_types = list(oth_r)
    common = sorted(set(ref_types) & set(oth_types))
    ref_only = sorted(set(ref_types) - set(oth_types))
    oth_only = sorted(set(oth_types) - set(ref_types))
    ref_w_c = _renorm(ref_w, common)
    oth_w_c = _renorm(oth_w, common)
    ref_obs = _observed(ref_r, ref_w)
    oth_obs = _observed(oth_r, oth_w)
    ref_obs_common = _dot(ref_r, ref_w_c, common)
    oth_obs_common = _dot(oth_r, oth_w_c, common)
    oth_on_ref = _dot(oth_r, ref_w_c, common)
    ref_on_oth = _dot(ref_r, oth_w_c, common)
    rate_effect = ref_obs_common - oth_on_ref
    mix_effect = oth_on_ref - oth_obs_common
    rows = []
    for btype in sorted(set(ref_types) | set(oth_types)):
        rows.append(
            {
                "building_type": btype,
                "in_reference": btype in ref_r,
                "in_other": btype in oth_r,
                "reference_rate": ref_r.get(btype),
                "other_rate": oth_r.get(btype),
                "reference_weight": ref_w.get(btype),
                "other_weight": oth_w.get(btype),
                f"in_{reference_id}": btype in ref_r,
                f"in_{other_id}": btype in oth_r,
                f"{reference_id}_rate": ref_r.get(btype),
                f"{other_id}_rate": oth_r.get(btype),
                f"{reference_id}_weight": ref_w.get(btype),
                f"{other_id}_weight": oth_w.get(btype),
            }
        )
    return {
        "weight": weight,
        "reference_id": reference_id,
        "other_id": other_id,
        "entity_classes": list(_ENTITY),
        "common_types": common,
        "reference_only_types": ref_only,
        "other_only_types": oth_only,
        "reference_observed": ref_obs,
        "other_observed": oth_obs,
        "reference_observed_common": ref_obs_common,
        "other_observed_common": oth_obs_common,
        "other_on_reference_mix": oth_on_ref,
        "reference_on_other_mix": ref_on_oth,
        f"{reference_id}_only_types": ref_only,
        f"{other_id}_only_types": oth_only,
        f"{reference_id}_observed": ref_obs,
        f"{other_id}_observed": oth_obs,
        f"{reference_id}_observed_common": ref_obs_common,
        f"{other_id}_observed_common": oth_obs_common,
        f"{other_id}_on_{reference_id}_mix": oth_on_ref,
        f"{reference_id}_on_{other_id}_mix": ref_on_oth,
        "gap": ref_obs - oth_obs,
        "gap_common": ref_obs_common - oth_obs_common,
        "rate_effect": rate_effect,
        "mix_effect": mix_effect,
        "types": rows,
        "caveat": (
            "Common building types only; mix weights renormalized to 1. "
            "Types that exist in only one metro are excluded from the "
            "standardized rates. Entity = llc + corp + partnership. "
            f"{reference_id} is the mix reference."
        ),
    }


def kitagawa_story(mix: dict[str, Any]) -> dict[str, Any]:
    """Which side of the common-type gap is larger: rate or mix."""
    rate = float(mix["rate_effect"])
    mix_effect = float(mix["mix_effect"])
    gap = float(mix["gap_common"])
    magnitude = abs(rate) + abs(mix_effect)
    dominant = "mix" if abs(mix_effect) >= abs(rate) else "rate"
    return {
        "dominant": dominant,
        "rate_effect": rate,
        "mix_effect": mix_effect,
        "gap_common": gap,
        "rate_share": abs(rate) / magnitude if magnitude else 0.0,
        "mix_share": abs(mix_effect) / magnitude if magnitude else 0.0,
        "reference_higher": float(mix["reference_observed"]) > float(mix["other_observed"]),
    }
