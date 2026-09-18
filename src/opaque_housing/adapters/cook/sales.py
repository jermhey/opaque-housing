"""Cook County Parcel Sales → canonical transfers.

Field names were verified against live ``wvhk-k5uv`` on 2026-09-18.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from opaque_housing.adapters.cook.parcels import format_pin
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import DocTypeCanonical

SOURCE_DATASET = "cook_sales"
SOURCE_VERSION = "wvhk-k5uv-2026-09-18"


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported Cook sales suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.lower() for name in df.columns})


def _parse_date(column: str) -> pl.Expr:
    text = pl.col(column).cast(pl.Utf8).fill_null("").str.slice(0, 10)
    return text.str.strptime(pl.Date, "%Y-%m-%d", strict=False)


def _is_non_sale_flag(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "t", "1", "yes"}


class CookSalesAdapter:
    metro_id = "cook"

    def __init__(self, source_version: str = SOURCE_VERSION) -> None:
        self.source_version = source_version
        self.filter_counts: list[FilterCount] = []

    def load_transfers(self, source_path: Path) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(source_path))
        if "pin" not in raw.columns:
            raise ValueError("Cook sales extract missing pin")
        rows_in = raw.height
        doc = (
            raw["doc_no"].cast(pl.Utf8)
            if "doc_no" in raw.columns
            else raw["row_id"].cast(pl.Utf8)
            if "row_id" in raw.columns
            else pl.col("pin").cast(pl.Utf8)
        )
        raw_type = (
            raw["mydec_deed_type"].cast(pl.Utf8)
            if "mydec_deed_type" in raw.columns
            else raw["deed_type"].cast(pl.Utf8)
            if "deed_type" in raw.columns
            else pl.lit("")
        )
        fallback_type = raw["deed_type"].cast(pl.Utf8) if "deed_type" in raw.columns else pl.lit("")
        recorded = (
            _parse_date("sale_date") if "sale_date" in raw.columns else pl.lit(None).cast(pl.Date)
        )
        amount = (
            raw["sale_price"].cast(pl.Float64, strict=False)
            if "sale_price" in raw.columns
            else pl.lit(None)
        )
        buyer = raw["buyer_name"].cast(pl.Utf8) if "buyer_name" in raw.columns else pl.lit(None)
        seller = raw["seller_name"].cast(pl.Utf8) if "seller_name" in raw.columns else pl.lit(None)
        flags = (
            [_is_non_sale_flag(value) for value in raw["sale_filter_deed_type"].to_list()]
            if "sale_filter_deed_type" in raw.columns
            else [False] * raw.height
        )
        typed = raw.with_columns(
            doc.alias("doc_id"),
            recorded.alias("recorded_date"),
            recorded.alias("doc_date"),
            pl.coalesce(raw_type.str.strip_chars(), fallback_type.str.strip_chars()).alias(
                "doc_type_raw"
            ),
            amount.alias("consideration"),
            buyer.alias("grantee_name_raw"),
            seller.alias("grantor_name_raw"),
            pl.col("pin").map_elements(format_pin, return_dtype=pl.Utf8).alias("parcel_id"),
            pl.Series("non_sale", flags, dtype=pl.Boolean),
        ).with_columns(
            pl.when(pl.col("non_sale"))
            .then(pl.lit(DocTypeCanonical.OTHER.value))
            .otherwise(pl.lit(DocTypeCanonical.SALE_DEED.value))
            .alias("doc_type_canonical")
        )
        result = (
            typed.group_by("doc_id", maintain_order=True)
            .agg(
                pl.col("recorded_date").first(),
                pl.col("doc_date").first(),
                pl.col("doc_type_raw").first(),
                pl.col("doc_type_canonical").first(),
                pl.col("consideration").first(),
                pl.col("grantee_name_raw").first(),
                pl.col("grantor_name_raw").first(),
                pl.col("parcel_id")
                .filter(pl.col("parcel_id") != "")
                .unique(maintain_order=True)
                .alias("parcel_ids"),
            )
            .with_columns(
                pl.lit(self.metro_id).alias("metro_id"),
                pl.lit(None).cast(pl.Float64).alias("percent_trans"),
                pl.lit(SOURCE_DATASET).alias("source_dataset"),
                pl.lit(self.source_version).alias("source_version"),
                pl.col("parcel_ids").fill_null(pl.lit([], dtype=pl.List(pl.Utf8))),
            )
            .select(
                "metro_id",
                "doc_id",
                "recorded_date",
                "doc_date",
                "doc_type_raw",
                "doc_type_canonical",
                "consideration",
                "percent_trans",
                "parcel_ids",
                "grantee_name_raw",
                "grantor_name_raw",
                "source_dataset",
                "source_version",
            )
        )
        self.filter_counts.append(
            FilterCount(
                stage="cook_sales_to_transfers",
                rule_id="group_document_parcels",
                rows_in=rows_in,
                rows_out=result.height,
            )
        )
        return result
