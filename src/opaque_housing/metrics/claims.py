"""Claim-card payloads from published headlines and sensitivity cubes."""

from __future__ import annotations

from typing import Any

import polars as pl

STOCK_SERIES = ("private_all", "sfr_condo")
STOCK_WEIGHTS = ("parcel", "unit")


def stock_sensitivity_table(headlines: dict[str, Any]) -> pl.DataFrame:
    """Four headline series × two weights. No reclassification."""
    rows: list[dict[str, Any]] = []
    correction = headlines.get("correction")
    if not isinstance(correction, dict):
        correction = {}
    for series in STOCK_SERIES:
        for include_trust in (False, True):
            key = f"{series}_entity_plus_trust" if include_trust else f"{series}_entity_only"
            block = headlines.get(key)
            if not isinstance(block, dict):
                continue
            corr_block = correction.get(key)
            if not isinstance(corr_block, dict):
                corr_block = {}
            for weight in STOCK_WEIGHTS:
                observed_key = "parcel_share" if weight == "parcel" else "unit_share"
                rates = corr_block.get(weight)
                if not isinstance(rates, dict):
                    rates = {}
                rows.append(
                    {
                        "series": series,
                        "include_trust": include_trust,
                        "weight": weight,
                        "headline_key": key,
                        "parcels": block.get("parcels"),
                        "units": block.get("units"),
                        "entity_parcels": block.get("entity_parcels"),
                        "entity_units": block.get("entity_units"),
                        "raw": block.get(observed_key),
                        "corrected": rates.get("corrected"),
                        "corrected_lo": rates.get("corrected_lo"),
                        "corrected_hi": rates.get("corrected_hi"),
                        "n_labeled": rates.get("n_labeled") or corr_block.get("n_labeled"),
                    }
                )
    return pl.DataFrame(rows)


def stock_claim(
    headlines: dict[str, Any],
    *,
    series: str = "private_all",
    weight: str = "parcel",
    include_trust: bool = False,
    window: str | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if series not in STOCK_SERIES:
        raise ValueError(f"unknown stock series {series}")
    if weight not in STOCK_WEIGHTS:
        raise ValueError("weight must be parcel or unit")
    table = stock_sensitivity_table(headlines)
    match = table.filter(
        (pl.col("series") == series)
        & (pl.col("weight") == weight)
        & (pl.col("include_trust") == include_trust)
    )
    if match.is_empty():
        raise KeyError(f"no stock slice {series} {weight} trust={include_trust}")
    row = match.row(0, named=True)
    trust_note = "entity + trust" if include_trust else "entity only (llc + corp + partnership)"
    weight_note = "lots" if weight == "parcel" else "units"
    caveat = (
        f"{trust_note}, {weight_note}-weighted. Trusts are not in the default headline. "
        "Public and nonprofit owners leave the private denominator."
    )
    if series == "sfr_condo":
        caveat += " Restricted to 1–4 family and condo units."
    if weight == "unit":
        caveat += " Philadelphia unit weights are official building-code lower bounds (ADR 0010)."
    if row.get("corrected") is None:
        caveat += " No gold correction on this slice."
    return {
        "kind": "stock",
        "label": f"{series.replace('_', ' ')} entity share",
        "series": series,
        "weight": weight,
        "include_trust": include_trust,
        "raw": row["raw"],
        "corrected": row["corrected"],
        "corrected_lo": row["corrected_lo"],
        "corrected_hi": row["corrected_hi"],
        "n_labeled": row["n_labeled"],
        "parcels": row["parcels"],
        "units": row["units"],
        "entity_parcels": row["entity_parcels"],
        "entity_units": row["entity_units"],
        "window": window,
        "filters": filters or [],
        "caveat": caveat,
    }


def flow_claim(
    sensitivity: pl.DataFrame,
    *,
    config: str = "default_10k",
    weight: str = "sale",
    window: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    extra_caveat: str = "",
) -> dict[str, Any]:
    if "config" not in sensitivity.columns:
        raise ValueError("flow_sensitivity missing config")
    match = sensitivity.filter(pl.col("config") == config)
    if match.is_empty():
        raise KeyError(f"no flow config {config}")
    row = match.row(0, named=True)
    if weight == "unit":
        raw = row.get("unit_share")
        count = row.get("units")
        entity_count = row.get("entity_units")
        label = "entity share of sale units"
    else:
        raw = row.get("sale_share")
        count = row.get("sales")
        entity_count = row.get("entity_sales")
        label = "entity share of sales"
    caveat = (
        f"Flow config {config}. Named grantee; entity = llc + corp + partnership. "
        "Membership-interest sales generate no deed."
    )
    if extra_caveat:
        caveat += " " + extra_caveat
    return {
        "kind": "flow",
        "label": label,
        "config": config,
        "weight": weight,
        "raw": raw,
        "corrected": None,
        "corrected_lo": None,
        "corrected_hi": None,
        "n_labeled": None,
        "sales": row.get("sales"),
        "entity_sales": row.get("entity_sales"),
        "units": row.get("units"),
        "entity_units": row.get("entity_units"),
        "count": count,
        "entity_count": entity_count,
        "min_consideration": row.get("min_consideration"),
        "window": window,
        "filters": filters or [],
        "caveat": caveat,
    }
