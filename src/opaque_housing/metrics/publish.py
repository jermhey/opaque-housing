"""Public-aggregate allowlist and neighborhood rollups. Pure functions; no I/O."""

from __future__ import annotations

from typing import Any

import polars as pl

from opaque_housing.metrics.correction import rogan_gladen
from opaque_housing.metrics.stock import INFORMATIVE_TYPES, MIN_PUBLISH_UNITS
from opaque_housing.schema import ENTITY_OWNED_CLASSES

_ENTITY = [item.value for item in ENTITY_OWNED_CLASSES]
_INFORMATIVE = list(INFORMATIVE_TYPES)

ALLOWED_FILES: frozenset[str] = frozenset(
    {
        "headlines.json",
        "stock_by_class.csv",
        "stock_by_building_type.csv",
        "stock_by_borough_type.csv",
        "stock_by_nta_type.csv",
        "run_manifest.json",
        "flow_headlines.json",
        "flow_by_year.csv",
        "flow_by_year_borough.csv",
        "flow_by_year_type.csv",
        "flow_sfr_condo_by_year.csv",
        "flow_sensitivity.csv",
        "history_by_year.csv",
        "consistency.json",
        "flow_manifest.json",
        "opacity_headlines.json",
        "opacity_by_type.csv",
        "opacity_manifest.json",
        "concentration_by_neighborhood.csv",
    }
)

GENERATED_FILES: frozenset[str] = frozenset(
    {
        "neighborhoods.csv",
        "nta_names.csv",
        "freshness.json",
        "site.json",
        "publish_manifest.json",
        "stock_sensitivity.csv",
    }
)

REQUIRED_FILES: frozenset[str] = frozenset(
    {
        "headlines.json",
        "stock_by_class.csv",
        "stock_by_building_type.csv",
        "stock_by_nta_type.csv",
    }
)

FORBIDDEN_FILENAMES: frozenset[str] = frozenset(
    {
        "parcels_classified.parquet",
        "parcels_opacity.parquet",
        "opacity_results.json",
        "owner_links.csv",
        "denied_addresses.csv",
        "llm_cache.duckdb",
    }
)

FORBIDDEN_COLUMNS: frozenset[str] = frozenset(
    {
        "owner_name",
        "ownername",
        "owner_name_raw",
        "name_raw",
        "name_normalized",
        "firstname",
        "lastname",
        "middleinitial",
        "address_1",
        "address1",
        "businesshousenumber",
        "businessstreetname",
        "corporationname",
        "contactdescription",
        "owner_key",
        "evidence_ref",
        "bbl",
        "parcel_id",
        "cluster_id",
        "person_key",
        "document_id",
        "chairman_name",
        "dos_process_name",
        "grantee_name_raw",
        "grantor_name_raw",
    }
)

NTA_BOROUGH: dict[str, str] = {
    "MN": "Manhattan",
    "BX": "Bronx",
    "BK": "Brooklyn",
    "QN": "Queens",
    "SI": "Staten Island",
}

MANIFEST_KEEP: tuple[str, ...] = (
    "metro_id",
    "started_at",
    "finished_at",
    "source_versions",
    "rules_version",
    "filter_counts",
    "notes",
)

MAX_STOCK_CHANGE = 0.20


class PublishError(ValueError):
    """A publish allowlist, leak, or quality-gate failure."""


def forbidden_columns(names: list[str]) -> list[str]:
    return sorted({name for name in names if name.lower() in FORBIDDEN_COLUMNS})


def assert_safe_columns(names: list[str], *, origin: str) -> None:
    leaked = forbidden_columns(names)
    if leaked:
        raise PublishError(f"{origin} has unpublished columns: {', '.join(leaked)}")


def assert_allowed_filename(name: str) -> None:
    if name in FORBIDDEN_FILENAMES:
        raise PublishError(f"{name} is not a public aggregate")
    if name not in ALLOWED_FILES and name not in GENERATED_FILES:
        raise PublishError(f"{name} is not on the publish allowlist")


def sanitize_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    """Drop local source paths. Keep versions, timestamps, and filter counts."""
    return {key: raw[key] for key in MANIFEST_KEEP if key in raw}


def stock_change_ratio(previous: int, current: int) -> float:
    if previous <= 0:
        return 0.0
    return abs(current - previous) / previous


def assert_stock_stable(
    previous_parcels: int | None,
    current_parcels: int,
    max_change: float = MAX_STOCK_CHANGE,
) -> None:
    if previous_parcels is None:
        return
    ratio = stock_change_ratio(previous_parcels, current_parcels)
    if ratio > max_change:
        raise PublishError(
            f"private parcel count changed {ratio:.1%} "
            f"({previous_parcels} -> {current_parcels}); max {max_change:.0%}"
        )


def nta_name_lookup(tract: pl.DataFrame) -> pl.DataFrame:
    """Unique NTA code / name / borough from the official equivalency table."""
    needed = {"ntacode", "ntaname", "boroname"}
    missing = needed - set(tract.columns)
    if missing:
        raise PublishError(f"tract–NTA table missing {sorted(missing)}")
    return (
        tract.select(
            pl.col("ntacode").cast(pl.Utf8).alias("nta"),
            pl.col("ntaname").cast(pl.Utf8).alias("nta_name"),
            pl.col("boroname").cast(pl.Utf8).alias("borough"),
        )
        .filter(pl.col("nta") != "")
        .unique(subset=["nta"], keep="first")
        .sort("nta")
    )


def _numeric_share_table(table: pl.DataFrame) -> pl.DataFrame:
    casts = []
    for col in ("class_parcels", "class_units", "parcels", "units"):
        if col in table.columns:
            casts.append(pl.col(col).cast(pl.Int64, strict=False).alias(col))
    return table.with_columns(casts) if casts else table


def entity_share_rollup(
    table: pl.DataFrame,
    geo_col: str,
    min_units: int = MIN_PUBLISH_UNITS,
) -> pl.DataFrame:
    """Roll a geo × building_type × owner_class table to one row per geo."""
    numeric = _numeric_share_table(table)
    type_totals = numeric.group_by([geo_col, "building_type"]).agg(
        pl.col("parcels").first(),
        pl.col("units").first(),
    )
    entity = (
        numeric.filter(pl.col("owner_class").is_in(_ENTITY))
        .group_by([geo_col, "building_type"])
        .agg(
            pl.col("class_parcels").sum().alias("entity_parcels"),
            pl.col("class_units").sum().alias("entity_units"),
        )
    )
    joined = type_totals.join(entity, on=[geo_col, "building_type"], how="left").with_columns(
        pl.col("entity_parcels").fill_null(0),
        pl.col("entity_units").fill_null(0),
    )

    def _sum(frame: pl.DataFrame) -> pl.DataFrame:
        return frame.group_by(geo_col).agg(
            pl.col("parcels").sum(),
            pl.col("units").sum(),
            pl.col("entity_parcels").sum(),
            pl.col("entity_units").sum(),
        )

    all_geo = _sum(joined)
    informative = _sum(joined.filter(pl.col("building_type").is_in(_INFORMATIVE))).rename(
        {
            "parcels": "sfr_condo_parcels",
            "units": "sfr_condo_units",
            "entity_parcels": "sfr_condo_entity_parcels",
            "entity_units": "sfr_condo_entity_units",
        }
    )
    out = all_geo.join(informative, on=geo_col, how="left")
    small = pl.col("units") < min_units
    info_small = pl.col("sfr_condo_units").fill_null(0) < min_units
    return out.with_columns(
        pl.when(small)
        .then(None)
        .otherwise(pl.col("entity_parcels") / pl.col("parcels"))
        .alias("entity_parcel_share"),
        pl.when(small)
        .then(None)
        .otherwise(pl.col("entity_units") / pl.col("units"))
        .alias("entity_unit_share"),
        pl.when(info_small)
        .then(None)
        .otherwise(pl.col("sfr_condo_entity_units") / pl.col("sfr_condo_units"))
        .alias("sfr_condo_entity_unit_share"),
        small.alias("suppressed"),
    )


def neighborhood_table(
    nta_type: pl.DataFrame,
    names: pl.DataFrame | None = None,
    min_units: int = MIN_PUBLISH_UNITS,
) -> pl.DataFrame:
    rolled = entity_share_rollup(nta_type, "geo_neighborhood", min_units=min_units).rename(
        {"geo_neighborhood": "nta"}
    )
    prefix = pl.col("nta").str.slice(0, 2)
    rolled = rolled.with_columns(prefix.replace_strict(NTA_BOROUGH, default=None).alias("borough"))
    if names is not None and names.height:
        rolled = rolled.join(names, on="nta", how="left", suffix="_lookup")
        if "nta_name" not in rolled.columns and "nta_name_lookup" in rolled.columns:
            rolled = rolled.rename({"nta_name_lookup": "nta_name"})
        if "borough_lookup" in rolled.columns:
            rolled = rolled.with_columns(
                pl.coalesce([pl.col("borough_lookup"), pl.col("borough")]).alias("borough")
            ).drop("borough_lookup")
    if "nta_name" not in rolled.columns:
        rolled = rolled.with_columns(pl.col("nta").alias("nta_name"))
    return rolled.select(
        "nta",
        "nta_name",
        "borough",
        "parcels",
        "units",
        "entity_parcels",
        "entity_units",
        "entity_parcel_share",
        "entity_unit_share",
        "sfr_condo_parcels",
        "sfr_condo_units",
        "sfr_condo_entity_parcels",
        "sfr_condo_entity_units",
        "sfr_condo_entity_unit_share",
        "suppressed",
    ).sort("nta")


def borough_table(borough_type: pl.DataFrame, min_units: int = MIN_PUBLISH_UNITS) -> pl.DataFrame:
    return (
        entity_share_rollup(borough_type, "geo_borough", min_units=min_units)
        .rename({"geo_borough": "borough"})
        .sort("borough")
    )


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return None if value != value else float(value)
    if isinstance(value, str):
        return value
    return value


def frame_records(table: pl.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in table.iter_rows(named=True):
        rows.append({key: _jsonable(val) for key, val in row.items()})
    return rows


def reattach_correction(
    headlines: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep gold rates when the labeled file is not on the runner."""
    if headlines.get("correction"):
        return headlines
    stored = (previous or {}).get("correction")
    if not isinstance(stored, dict):
        return headlines
    block: dict[str, Any] = {}
    for key, payload in headlines.items():
        if key == "correction" or not isinstance(payload, dict):
            continue
        prior = stored.get(key)
        if not isinstance(prior, dict):
            continue
        series: dict[str, Any] = {
            "n_labeled": prior.get("n_labeled"),
            "positive_includes_trust": prior.get("positive_includes_trust"),
            "rates_reused": True,
        }
        for weight in ("unit", "parcel"):
            rates = prior.get(weight)
            if not isinstance(rates, dict):
                continue
            observed_key = "unit_share" if weight == "unit" else "parcel_share"
            observed = float(payload[observed_key])
            sens = float(rates["sensitivity"])
            spec = float(rates["specificity"])
            series[weight] = {
                "observed": observed,
                "sensitivity": sens,
                "specificity": spec,
                "n_labeled": rates.get("n_labeled"),
                "corrected": rogan_gladen(observed, sens, spec),
                "corrected_lo": None,
                "corrected_hi": None,
                "n_boot": 0.0,
            }
        block[key] = series
    if not block:
        return headlines
    return {**headlines, "correction": block}


def assemble_site_payload(
    *,
    metro: str,
    generated_at: str,
    headlines: dict[str, Any],
    neighborhoods: pl.DataFrame,
    boroughs: pl.DataFrame | None = None,
    stock_by_class: pl.DataFrame | None = None,
    stock_by_type: pl.DataFrame | None = None,
    flow_headlines: dict[str, Any] | None = None,
    flow_by_year: pl.DataFrame | None = None,
    flow_sfr_condo: pl.DataFrame | None = None,
    flow_sensitivity: pl.DataFrame | None = None,
    history_by_year: pl.DataFrame | None = None,
    consistency: dict[str, Any] | None = None,
    opacity_headlines: dict[str, Any] | None = None,
    opacity_by_type: pl.DataFrame | None = None,
    freshness: dict[str, Any] | None = None,
    reused: dict[str, str] | None = None,
    concentration: pl.DataFrame | None = None,
    stock_sensitivity: pl.DataFrame | None = None,
) -> dict[str, Any]:
    return {
        "metro": metro,
        "generated_at": generated_at,
        "reused": reused or {},
        "stock": headlines,
        "neighborhoods": frame_records(neighborhoods),
        "boroughs": frame_records(boroughs) if boroughs is not None else [],
        "stock_by_class": frame_records(stock_by_class) if stock_by_class is not None else [],
        "stock_by_type": frame_records(stock_by_type) if stock_by_type is not None else [],
        "flow": flow_headlines or {},
        "flow_by_year": frame_records(flow_by_year) if flow_by_year is not None else [],
        "flow_sfr_condo": frame_records(flow_sfr_condo) if flow_sfr_condo is not None else [],
        "flow_sensitivity": frame_records(flow_sensitivity) if flow_sensitivity is not None else [],
        "history": frame_records(history_by_year) if history_by_year is not None else [],
        "consistency": consistency or {},
        "opacity": opacity_headlines or {},
        "opacity_by_type": frame_records(opacity_by_type) if opacity_by_type is not None else [],
        "freshness": freshness or {},
        "concentration": frame_records(concentration) if concentration is not None else [],
        "stock_sensitivity": (
            frame_records(stock_sensitivity) if stock_sensitivity is not None else []
        ),
    }
