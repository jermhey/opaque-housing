"""DCP PAD billing-lot ↔ unit-lot crosswalk.

Official BBL-file fields are from padlayout.pdf (2026-09-17 fetch):
boro, block, lot, billboro, billblock, billlot, condoflag, plus the
lo/hi condo range fields. SODA bc8t-ecyu is 403; guessed zip URLs 404.

Condo complexes are stored as a lo–hi lot range on one row. We keep that
range and match incoming BBLs against it instead of exploding every lot.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.bbl import format_bbl_parts

REQUIRED = ("boro", "block", "lot")


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv", ".txt"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported PAD extract suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.lower() for name in df.columns})


def _bbl_series(df: pl.DataFrame, boro: str, block: str, lot: str, out: str) -> pl.DataFrame:
    values = [
        format_bbl_parts(row[boro], row[block], row[lot])
        for row in df.select([boro, block, lot]).iter_rows(named=True)
    ]
    return df.with_columns(pl.Series(out, values, dtype=pl.Utf8))


def _int_expr(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.Utf8).cast(pl.Float64, strict=False).cast(pl.Int64)


def parse_bbl_parts(parcel_id: str) -> tuple[int | None, int | None, int | None]:
    text = (parcel_id or "").strip()
    if len(text) != 10 or not text.isdigit():
        return None, None, None
    return int(text[0]), int(text[1:6]), int(text[6:10])


def crosswalk_from_frame(raw: pl.DataFrame) -> pl.DataFrame:
    work = _normalize_columns(raw)
    missing = [col for col in REQUIRED if col not in work.columns]
    if missing:
        raise ValueError(f"PAD extract missing required columns: {missing}")
    work = _bbl_series(work, "boro", "block", "lot", "unit_parcel_id")
    if all(col in work.columns for col in ("billboro", "billblock", "billlot")):
        work = _bbl_series(work, "billboro", "billblock", "billlot", "billing_parcel_id")
        work = work.with_columns(
            pl.when(pl.col("billing_parcel_id") == "")
            .then(pl.col("unit_parcel_id"))
            .otherwise(pl.col("billing_parcel_id"))
            .alias("billing_parcel_id")
        )
    else:
        work = work.with_columns(pl.col("unit_parcel_id").alias("billing_parcel_id"))

    for col, alias in (
        ("loboro", "lo_boro"),
        ("loblock", "lo_block"),
        ("lolot", "lo_lot"),
        ("hiboro", "hi_boro"),
        ("hiblock", "hi_block"),
        ("hilot", "hi_lot"),
    ):
        work = work.with_columns(
            (_int_expr(col) if col in work.columns else pl.lit(None).cast(pl.Int64)).alias(alias)
        )

    flag = (
        pl.col("condoflag").cast(pl.Utf8).str.to_uppercase()
        if "condoflag" in work.columns
        else pl.lit("")
    )
    return (
        work.with_columns(flag.alias("condoflag"))
        .filter(pl.col("unit_parcel_id") != "")
        .select(
            "unit_parcel_id",
            "billing_parcel_id",
            "condoflag",
            "lo_boro",
            "lo_block",
            "lo_lot",
            "hi_boro",
            "hi_block",
            "hi_lot",
        )
    )


def load_pad_crosswalk(path: Path) -> pl.DataFrame:
    return crosswalk_from_frame(_read_table(path))


def map_to_billing(parcel_ids: pl.Series, crosswalk: pl.DataFrame) -> pl.DataFrame:
    """Return unit_parcel_id / billing_parcel_id / is_condo_unit for each id."""
    units = pl.DataFrame({"unit_parcel_id": parcel_ids.cast(pl.Utf8)}).with_columns(
        pl.col("unit_parcel_id").alias("_pid")
    )
    parts = [parse_bbl_parts(pid) for pid in units["_pid"].to_list()]
    units = units.with_columns(
        pl.Series("boro", [p[0] for p in parts], dtype=pl.Int64),
        pl.Series("block", [p[1] for p in parts], dtype=pl.Int64),
        pl.Series("lot", [p[2] for p in parts], dtype=pl.Int64),
    ).drop("_pid")

    exact = units.join(crosswalk, on="unit_parcel_id", how="left")
    billed = pl.col("billing_parcel_id")
    have = exact.filter(billed.is_not_null() & (billed != ""))
    unmatched = exact.filter(billed.is_null() | (billed == "")).select("unit_parcel_id")
    need = units.join(unmatched, on="unit_parcel_id", how="inner")
    if need.height and {"lo_boro", "lo_block", "lo_lot", "hi_lot"} <= set(crosswalk.columns):
        condos = crosswalk.filter(pl.col("condoflag") == "C")
        ranged = need.join(
            condos,
            left_on=["boro", "block"],
            right_on=["lo_boro", "lo_block"],
            how="inner",
        ).filter(
            pl.col("lo_lot").is_not_null()
            & (pl.col("lot") >= pl.col("lo_lot"))
            & (pl.col("lot") <= pl.col("hi_lot"))
        )
        ranged = ranged.unique(subset=["unit_parcel_id"], keep="first")
        have = pl.concat(
            [
                have.select("unit_parcel_id", "billing_parcel_id", "condoflag"),
                ranged.select("unit_parcel_id", "billing_parcel_id", "condoflag"),
            ],
            how="vertical",
        )
    else:
        have = have.select("unit_parcel_id", "billing_parcel_id", "condoflag")

    joined = units.select("unit_parcel_id").join(have, on="unit_parcel_id", how="left")
    billing = (
        pl.when(pl.col("billing_parcel_id").is_null() | (pl.col("billing_parcel_id") == ""))
        .then(pl.col("unit_parcel_id"))
        .otherwise(pl.col("billing_parcel_id"))
    )
    return joined.with_columns(
        billing.alias("billing_parcel_id"),
        ((pl.col("condoflag") == "C") & (billing != pl.col("unit_parcel_id"))).alias(
            "is_condo_unit"
        ),
    )
