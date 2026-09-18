"""Entity-buyer flow shares. Pure functions on classified sale frames."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import polars as pl

from opaque_housing.adapters.nyc.pad import map_to_billing
from opaque_housing.classify.apply import classify_name_frame
from opaque_housing.metrics.sale_filter import SaleFilterConfig, apply_sale_filter
from opaque_housing.metrics.stock import INFORMATIVE_TYPES, nyc_borough
from opaque_housing.metros import metro_spec
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import ENTITY_OWNED_CLASSES

_ENTITY = [item.value for item in ENTITY_OWNED_CLASSES]
WINDOW_START = 2003
WINDOW_END = 2025


def classify_buyers(sales: pl.DataFrame) -> pl.DataFrame:
    classified = classify_name_frame(sales, name_col="grantee_name_raw", out_prefix="buyer_")
    return classified.rename(
        {
            "buyer_owner_class": "buyer_class",
            "buyer_name_normalized": "buyer_name_normalized",
            "buyer_owner_key": "buyer_owner_key",
            "buyer_rule_id": "buyer_rule_id",
            "buyer_class_source": "buyer_class_source",
        }
    ).with_columns(pl.col("buyer_class").is_in(_ENTITY).alias("is_entity"))


def explode_parcels(sales: pl.DataFrame) -> pl.DataFrame:
    return (
        sales.explode("parcel_ids", empty_as_null=True)
        .rename({"parcel_ids": "parcel_id"})
        .filter(pl.col("parcel_id").cast(pl.Utf8).fill_null("") != "")
        .unique(subset=["doc_id", "parcel_id"], keep="first")
    )


def attach_residential(
    sales: pl.DataFrame,
    parcels: pl.DataFrame,
    pad: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, list[FilterCount]]:
    """Keep sales that touch at least one residential lot. Condo units count as 1."""
    long = explode_parcels(sales)
    rows_in = sales.height
    if long.is_empty():
        empty = sales.clear().with_columns(
            pl.lit(None).cast(pl.Utf8).alias("parcel_id"),
            pl.lit(None).cast(pl.Utf8).alias("building_type"),
            pl.lit(None).cast(pl.Int64).alias("res_units"),
            pl.lit(None).cast(pl.Utf8).alias("geo_tract"),
            pl.lit(None).cast(pl.Utf8).alias("geo_neighborhood"),
            pl.lit(None).cast(pl.Utf8).alias("geo_borough"),
        )
        count = FilterCount(
            stage="flow_residential_join",
            rule_id="pluto_or_pad_residential",
            rows_in=rows_in,
            rows_out=0,
        )
        return empty, [count]

    parcel_cols = ["parcel_id", "building_type", "res_units", "geo_tract", "geo_neighborhood"]
    if "geo_borough" in parcels.columns:
        parcel_cols.append("geo_borough")
    parcel_attrs = parcels.select(parcel_cols)
    if pad is not None and pad.height:
        mapped = map_to_billing(long["parcel_id"], pad)
        long = long.join(mapped, left_on="parcel_id", right_on="unit_parcel_id", how="left")
        long = long.with_columns(
            pl.col("billing_parcel_id").fill_null(pl.col("parcel_id")).alias("join_parcel_id"),
            pl.col("is_condo_unit").fill_null(False),
        )
    else:
        long = long.with_columns(
            pl.col("parcel_id").alias("join_parcel_id"),
            pl.lit(False).alias("is_condo_unit"),
        )

    direct = long.join(parcel_attrs, on="parcel_id", how="left")
    have = direct.filter(pl.col("building_type").is_not_null())
    need = direct.filter(pl.col("building_type").is_null()).drop(
        [
            col
            for col in (
                "building_type",
                "res_units",
                "geo_tract",
                "geo_neighborhood",
                "geo_borough",
            )
            if col in direct.columns
        ]
    )
    filled = need.join(
        parcel_attrs,
        left_on="join_parcel_id",
        right_on="parcel_id",
        how="left",
    )
    attached = pl.concat([have, filled], how="diagonal")
    attached = attached.unique(subset=["doc_id", "parcel_id"], keep="first")
    attached = attached.with_columns(
        pl.when(pl.col("is_condo_unit"))
        .then(pl.lit("condo_unit"))
        .otherwise(pl.col("building_type"))
        .alias("building_type"),
        pl.when(pl.col("is_condo_unit"))
        .then(pl.lit(1))
        .otherwise(pl.col("res_units"))
        .alias("res_units"),
    )
    matched = attached.filter(pl.col("building_type").is_not_null())
    keep_ids = set(matched["doc_id"].to_list())
    kept_sales = sales.filter(pl.col("doc_id").is_in(list(keep_ids)))
    counts = [
        FilterCount(
            stage="flow_residential_join",
            rule_id="pluto_or_pad_residential",
            rows_in=rows_in,
            rows_out=kept_sales.height,
        )
    ]
    return matched, counts


def with_year_and_borough(matched: pl.DataFrame) -> pl.DataFrame:
    """Prefer adapter-supplied ``geo_borough`` (ADR 0010). NYC BBL is the fallback."""
    years = matched.with_columns(pl.col("recorded_date").dt.year().alias("year"))
    if "geo_borough" in years.columns and years["geo_borough"].null_count() < years.height:
        return years
    boroughs = [nyc_borough(pid or "") for pid in years["parcel_id"].to_list()]
    return years.with_columns(pl.Series("geo_borough", boroughs, dtype=pl.Utf8))


def in_coverage_window(
    frame: pl.DataFrame,
    start: int = WINDOW_START,
    end: int = WINDOW_END,
) -> tuple[pl.DataFrame, FilterCount]:
    rows_in = frame.height
    kept = frame.filter(pl.col("year").is_between(start, end, closed="both"))
    return kept, FilterCount(
        stage="coverage_window",
        rule_id=f"recorded_year_{start}_{end}",
        rows_in=rows_in,
        rows_out=kept.height,
    )


def _sale_level(matched: pl.DataFrame) -> pl.DataFrame:
    """One row per document; unit weight is the sum of matched residential units."""
    return matched.group_by("doc_id").agg(
        pl.col("year").first(),
        pl.col("is_entity").first(),
        pl.col("buyer_class").first(),
        pl.col("consideration").first(),
        pl.col("building_type").first(),
        pl.col("geo_borough").first(),
        pl.col("res_units").sum().alias("res_units"),
        pl.len().alias("n_parcels"),
    )


def flow_share_table(matched: pl.DataFrame, group: list[str]) -> pl.DataFrame:
    sales = _sale_level(matched)
    if sales.is_empty():
        schema = {
            **{name: pl.Int64 if name == "year" else pl.Utf8 for name in group},
            "sales": pl.UInt32,
            "entity_sales": pl.UInt32,
            "units": pl.Int64,
            "entity_units": pl.Int64,
            "sale_share": pl.Float64,
            "unit_share": pl.Float64,
        }
        return pl.DataFrame(schema=schema)
    if group:
        totals = sales.group_by(group).agg(
            pl.len().alias("sales"),
            pl.col("res_units").sum().alias("units"),
        )
        entity = (
            sales.filter(pl.col("is_entity"))
            .group_by(group)
            .agg(
                pl.len().alias("entity_sales"),
                pl.col("res_units").sum().alias("entity_units"),
            )
        )
        joined = totals.join(entity, on=group, how="left")
    else:
        totals = sales.select(
            pl.len().alias("sales"),
            pl.col("res_units").sum().alias("units"),
        )
        entity_sales = sales.filter(pl.col("is_entity"))
        joined = totals.with_columns(
            pl.lit(entity_sales.height).alias("entity_sales"),
            pl.lit(int(entity_sales["res_units"].sum() or 0)).alias("entity_units"),
        )
    result = joined.with_columns(
        pl.col("entity_sales").fill_null(0),
        pl.col("entity_units").fill_null(0),
        (pl.col("entity_sales").fill_null(0) / pl.col("sales")).alias("sale_share"),
        pl.when(pl.col("units") > 0)
        .then(pl.col("entity_units").fill_null(0) / pl.col("units"))
        .otherwise(None)
        .alias("unit_share"),
    )
    return result.sort(group) if group else result


def flow_breakdowns(matched: pl.DataFrame) -> dict[str, pl.DataFrame]:
    return {
        "by_year": flow_share_table(matched, ["year"]),
        "by_year_type": flow_share_table(matched, ["year", "building_type"]),
        "by_year_borough": flow_share_table(matched, ["year", "geo_borough"]),
        "sfr_condo_by_year": flow_share_table(
            matched.filter(pl.col("building_type").is_in(list(INFORMATIVE_TYPES))),
            ["year"],
        ),
    }


def flow_headlines(
    matched: pl.DataFrame,
    start: int = WINDOW_START,
    end: int = WINDOW_END,
) -> dict[str, Any]:
    city = flow_share_table(matched, [])
    informative = flow_share_table(
        matched.filter(pl.col("building_type").is_in(list(INFORMATIVE_TYPES))),
        [],
    )

    def _row(table: pl.DataFrame) -> dict[str, Any]:
        if table.is_empty():
            return {
                "sales": 0,
                "entity_sales": 0,
                "units": 0,
                "entity_units": 0,
                "sale_share": 0.0,
                "unit_share": 0.0,
            }
        row = table.to_dicts()[0]
        return {k: row[k] for k in row if k not in {"year", "building_type", "geo_borough"}}

    return {
        "window": {"start": start, "end": end},
        "private_residential": _row(city),
        "sfr_condo": _row(informative),
    }


SENSITIVITY_CONFIGS: list[tuple[str, SaleFilterConfig]] = [
    ("default_10k", SaleFilterConfig()),
    ("threshold_0", SaleFilterConfig(min_consideration=0.0)),
    ("threshold_1", SaleFilterConfig(min_consideration=1.0)),
    ("threshold_100k", SaleFilterConfig(min_consideration=100_000.0)),
    ("zero_as_missing_10k", SaleFilterConfig(treat_zero_amount_as_missing=True)),
    ("exclude_same_surname", SaleFilterConfig(exclude_same_surname=True)),
    ("require_full_interest", SaleFilterConfig(require_full_interest=True)),
    ("exclude_astu", SaleFilterConfig(drop_sale_codes=frozenset({"ASTU"}))),
    ("exclude_deedo", SaleFilterConfig(drop_sale_codes=frozenset({"DEEDO"}))),
]

PHL_SENSITIVITY_CONFIGS: list[tuple[str, SaleFilterConfig]] = [
    ("default_10k", SaleFilterConfig()),
    ("threshold_0", SaleFilterConfig(min_consideration=0.0)),
    ("threshold_1", SaleFilterConfig(min_consideration=1.0)),
    ("threshold_100k", SaleFilterConfig(min_consideration=100_000.0)),
    ("zero_as_missing_10k", SaleFilterConfig(treat_zero_amount_as_missing=True)),
    ("exclude_same_surname", SaleFilterConfig(exclude_same_surname=True)),
    ("require_full_interest", SaleFilterConfig(require_full_interest=True)),
    (
        "exclude_sheriff",
        SaleFilterConfig(drop_sale_codes=frozenset({"DEED SHERIFF", "SHERIFF'S DEED"})),
    ),
]

COOK_SENSITIVITY_CONFIGS: list[tuple[str, SaleFilterConfig]] = [
    ("default_10k", SaleFilterConfig()),
    ("threshold_0", SaleFilterConfig(min_consideration=0.0)),
    ("threshold_1", SaleFilterConfig(min_consideration=1.0)),
    ("threshold_100k", SaleFilterConfig(min_consideration=100_000.0)),
    ("zero_as_missing_10k", SaleFilterConfig(treat_zero_amount_as_missing=True)),
    (
        "exclude_quit_claim",
        SaleFilterConfig(drop_sale_codes=frozenset({"Quit claim", "Quit Claim Deed"})),
    ),
]

DADE_SENSITIVITY_CONFIGS: list[tuple[str, SaleFilterConfig]] = [
    ("default_10k", SaleFilterConfig(require_named_grantee=False)),
    ("threshold_0", SaleFilterConfig(min_consideration=0.0, require_named_grantee=False)),
    ("threshold_1", SaleFilterConfig(min_consideration=1.0, require_named_grantee=False)),
    ("threshold_100k", SaleFilterConfig(min_consideration=100_000.0, require_named_grantee=False)),
]

_SENSITIVITY_PROFILES: dict[str, list[tuple[str, SaleFilterConfig]] | None] = {
    "nyc": None,
    "phl": PHL_SENSITIVITY_CONFIGS,
    "cook": COOK_SENSITIVITY_CONFIGS,
    "dade": DADE_SENSITIVITY_CONFIGS,
}


def sensitivity_configs_for(metro: str) -> list[tuple[str, SaleFilterConfig]] | None:
    """Select a precomputed sensitivity table from MetroSpec.sensitivity_profile."""
    profile = metro_spec(metro).sensitivity_profile
    if profile not in _SENSITIVITY_PROFILES:
        raise KeyError(profile)
    return _SENSITIVITY_PROFILES[profile]


def sensitivity_table(
    transfers: pl.DataFrame,
    parcels: pl.DataFrame,
    pad: pl.DataFrame | None = None,
    configs: list[tuple[str, SaleFilterConfig]] | None = None,
    start: int = WINDOW_START,
    end: int = WINDOW_END,
) -> pl.DataFrame:
    # Classify the widest named-grantee sale set once; each config is a row filter.
    if "buyer_class" in transfers.columns:
        classified = transfers
    else:
        widest, _ = history_only_sales(transfers)
        classified = classify_buyers(widest)
    rows: list[dict[str, Any]] = []
    for name, config in configs or SENSITIVITY_CONFIGS:
        filtered, _ = apply_sale_filter(classified, config)
        matched, _ = attach_residential(filtered, parcels, pad)
        matched = with_year_and_borough(matched)
        matched, _ = in_coverage_window(matched, start, end)
        headlines = flow_headlines(matched, start, end)
        payload = headlines["private_residential"]
        rows.append(
            {
                "config": name,
                **asdict(config),
                "drop_sale_codes": ",".join(sorted(config.drop_sale_codes)),
                "sales": payload["sales"],
                "entity_sales": payload["entity_sales"],
                "sale_share": payload["sale_share"],
                "units": payload["units"],
                "entity_units": payload["entity_units"],
                "unit_share": payload["unit_share"],
            }
        )
    return pl.DataFrame(rows)


def history_only_sales(transfers: pl.DataFrame) -> tuple[pl.DataFrame, list[FilterCount]]:
    """Sale deeds with a named grantee — no amount cut (ADR 0005)."""
    return apply_sale_filter(
        transfers,
        SaleFilterConfig(min_consideration=0.0, treat_zero_amount_as_missing=True),
    )
