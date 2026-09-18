"""Anonymous neighborhood concentration. Pure; never emits keys or names."""

from __future__ import annotations

import polars as pl

from opaque_housing.metrics.stock import MIN_PUBLISH_UNITS

CONCENTRATION_COLUMNS: tuple[str, ...] = (
    "geo_neighborhood",
    "parcels",
    "units",
    "n_name_keys",
    "hhi_parcels",
    "hhi_units",
    "top5_parcel_share",
    "top5_unit_share",
    "top10_parcel_share",
    "top10_unit_share",
    "top20_parcel_share",
    "top20_unit_share",
    "suppressed",
)

_TOP_N = (5, 10, 20)


def _cluster_expr(frame: pl.DataFrame) -> pl.Expr:
    """Name-key, or opacity cluster_id when present. Blank keys stay unmerged."""
    if "parcel_id" in frame.columns:
        blank = pl.concat_str([pl.lit("_blank:"), pl.col("parcel_id").cast(pl.Utf8)])
    else:
        blank = pl.concat_str([pl.lit("_blank:"), pl.col("_row").cast(pl.Utf8)])
    owner = None
    if "owner_key" in frame.columns:
        owner = pl.col("owner_key").cast(pl.Utf8).fill_null("")
    if owner is None:
        return blank
    if "cluster_id" in frame.columns:
        cluster = pl.col("cluster_id").cast(pl.Utf8).fill_null("")
        return pl.when(cluster != "").then(cluster).when(owner != "").then(owner).otherwise(blank)
    return pl.when(owner != "").then(owner).otherwise(blank)


def neighborhood_concentration(
    private: pl.DataFrame,
    min_units: int = MIN_PUBLISH_UNITS,
) -> pl.DataFrame:
    """HHI and top-N shares by neighborhood. Output has no owner_key or names."""
    empty = pl.DataFrame(
        schema={
            "geo_neighborhood": pl.Utf8,
            "parcels": pl.UInt32,
            "units": pl.Int64,
            "n_name_keys": pl.UInt32,
            "hhi_parcels": pl.Float64,
            "hhi_units": pl.Float64,
            "top5_parcel_share": pl.Float64,
            "top5_unit_share": pl.Float64,
            "top10_parcel_share": pl.Float64,
            "top10_unit_share": pl.Float64,
            "top20_parcel_share": pl.Float64,
            "top20_unit_share": pl.Float64,
            "suppressed": pl.Boolean,
        }
    )
    if private.is_empty():
        return empty
    if "geo_neighborhood" not in private.columns:
        raise ValueError("classified parcels need geo_neighborhood")
    if "res_units" not in private.columns:
        raise ValueError("classified parcels need res_units")
    work = private.with_row_index("_row").with_columns(
        pl.col("geo_neighborhood").cast(pl.Utf8).fill_null("").alias("geo_neighborhood"),
        pl.col("res_units").cast(pl.Int64, strict=False).fill_null(0),
    )
    work = work.with_columns(_cluster_expr(work).alias("_cluster"))
    by_owner = work.group_by(["geo_neighborhood", "_cluster"]).agg(
        pl.len().alias("owner_parcels"),
        pl.col("res_units").sum().alias("owner_units"),
    )
    totals = work.group_by("geo_neighborhood").agg(
        pl.len().alias("parcels"),
        pl.col("res_units").sum().alias("units"),
        pl.col("_cluster").n_unique().alias("n_name_keys"),
    )
    shares = by_owner.join(totals, on="geo_neighborhood").with_columns(
        pl.when(pl.col("parcels") > 0)
        .then(pl.col("owner_parcels") / pl.col("parcels"))
        .otherwise(0.0)
        .alias("p_share"),
        pl.when(pl.col("units") > 0)
        .then(pl.col("owner_units") / pl.col("units"))
        .otherwise(0.0)
        .alias("u_share"),
    )
    hhi = shares.group_by("geo_neighborhood").agg(
        (pl.col("p_share") ** 2).sum().alias("hhi_parcels"),
        (pl.col("u_share") ** 2).sum().alias("hhi_units"),
    )
    ranked = shares.with_columns(
        pl.col("owner_parcels")
        .rank(method="ordinal", descending=True)
        .over("geo_neighborhood")
        .alias("parcel_rank"),
        pl.col("owner_units")
        .rank(method="ordinal", descending=True)
        .over("geo_neighborhood")
        .alias("unit_rank"),
    )
    out = totals.join(hhi, on="geo_neighborhood", how="left")
    for count in _TOP_N:
        parcel_top = (
            ranked.filter(pl.col("parcel_rank") <= count)
            .group_by("geo_neighborhood")
            .agg(pl.col("p_share").sum().alias(f"top{count}_parcel_share"))
        )
        unit_top = (
            ranked.filter(pl.col("unit_rank") <= count)
            .group_by("geo_neighborhood")
            .agg(pl.col("u_share").sum().alias(f"top{count}_unit_share"))
        )
        out = out.join(parcel_top, on="geo_neighborhood", how="left").join(
            unit_top, on="geo_neighborhood", how="left"
        )
    small = pl.col("units") < min_units
    share_cols = [
        "hhi_parcels",
        "hhi_units",
        "top5_parcel_share",
        "top5_unit_share",
        "top10_parcel_share",
        "top10_unit_share",
        "top20_parcel_share",
        "top20_unit_share",
    ]
    nulled = [pl.when(small).then(None).otherwise(pl.col(name)).alias(name) for name in share_cols]
    return (
        out.with_columns(*nulled, small.alias("suppressed"))
        .select(list(CONCENTRATION_COLUMNS))
        .sort("geo_neighborhood")
    )
