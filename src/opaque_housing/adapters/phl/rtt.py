"""Philadelphia RTT_SUMMARY → canonical transfers.

Field names were verified against live ``rtt_summary`` on 2026-09-17.
"""

from pathlib import Path

import polars as pl

from opaque_housing.adapters.phl.opa import format_parcel_number
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import DocTypeCanonical

SOURCE_DATASET = "phl_rtt"
SOURCE_VERSION = "rtt_summary-2026-09-17"
# Live labels. SHERIFF'S DEED is the same instrument as DEED SHERIFF (ADR 0010).
SALE_TYPES = frozenset({"DEED", "DEED SHERIFF", "SHERIFF'S DEED"})


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported RTT extract suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.lower() for name in df.columns})


def _parse_date_expr(column: str) -> pl.Expr:
    text = pl.col(column).cast(pl.Utf8).fill_null("").str.slice(0, 10)
    return text.str.strptime(pl.Date, "%Y-%m-%d", strict=False)


class PhlRttAdapter:
    metro_id = "phl"

    def __init__(self, source_version: str = SOURCE_VERSION) -> None:
        self.source_version = source_version
        self.filter_counts: list[FilterCount] = []

    def load_transfers(self, source_path: Path) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(source_path))
        required = ("document_id", "document_type", "grantees")
        missing = [col for col in required if col not in raw.columns]
        if missing:
            raise ValueError(f"RTT extract missing required columns: {missing}")
        rows_in = raw.height
        recorded = (
            _parse_date_expr("recording_date")
            if "recording_date" in raw.columns
            else pl.lit(None).cast(pl.Date)
        )
        display = (
            _parse_date_expr("display_date")
            if "display_date" in raw.columns
            else pl.lit(None).cast(pl.Date)
        )
        grantors = (
            raw["grantors"].cast(pl.Utf8)
            if "grantors" in raw.columns
            else pl.lit(None).cast(pl.Utf8)
        )
        amounts = (
            raw["total_consideration"].cast(pl.Float64, strict=False)
            if "total_consideration" in raw.columns
            else pl.lit(None)
        )
        parcels = (
            raw["opa_account_num"].map_elements(format_parcel_number, return_dtype=pl.Utf8)
            if "opa_account_num" in raw.columns
            else pl.lit("")
        )
        typed = raw.with_columns(
            pl.col("document_id").cast(pl.Utf8).alias("doc_id"),
            recorded.alias("recorded_date"),
            display.alias("doc_date"),
            pl.col("document_type").cast(pl.Utf8).str.strip_chars().alias("doc_type_raw"),
            amounts.alias("consideration"),
            pl.col("grantees").cast(pl.Utf8).alias("grantee_name_raw"),
            grantors.alias("grantor_name_raw"),
            parcels.alias("parcel_id"),
        ).with_columns(
            pl.when(pl.col("doc_type_raw").str.to_uppercase().is_in(list(SALE_TYPES)))
            .then(pl.lit(DocTypeCanonical.SALE_DEED.value))
            .otherwise(pl.lit(DocTypeCanonical.OTHER.value))
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
                stage="rtt_to_transfers",
                rule_id="group_document_parcels",
                rows_in=rows_in,
                rows_out=result.height,
            )
        )
        return result
