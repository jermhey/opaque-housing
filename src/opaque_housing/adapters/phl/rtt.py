"""Philadelphia RTT_SUMMARY → transfer rows.

Field names were verified against live ``rtt_summary`` on 2026-09-17.
"""

from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import DocTypeCanonical

SOURCE_DATASET = "phl_rtt"
SALE_TYPES = frozenset({"DEED"})


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported RTT extract suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.lower() for name in df.columns})


def _parse_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


class PhlRttAdapter:
    metro_id = "phl"

    def __init__(self) -> None:
        self.filter_counts: list[FilterCount] = []

    def load_transfers(self, source_path: Path) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(source_path))
        required = ("document_id", "document_type", "grantees")
        missing = [col for col in required if col not in raw.columns]
        if missing:
            raise ValueError(f"RTT extract missing required columns: {missing}")
        rows_in = raw.height
        if "recording_date" in raw.columns:
            recorded_src = raw["recording_date"].to_list()
        else:
            recorded_src = [None] * raw.height
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
            raw["opa_account_num"].cast(pl.Utf8).fill_null("")
            if "opa_account_num" in raw.columns
            else pl.lit("")
        )
        result = raw.with_columns(
            pl.lit(self.metro_id).alias("metro_id"),
            pl.col("document_id").cast(pl.Utf8).alias("doc_id"),
            pl.Series("recorded_date", [_parse_date(value) for value in recorded_src]),
            pl.col("document_type").cast(pl.Utf8).alias("doc_type_raw"),
            pl.when(
                pl.col("document_type").cast(pl.Utf8).str.to_uppercase().is_in(list(SALE_TYPES))
            )
            .then(pl.lit(DocTypeCanonical.SALE_DEED.value))
            .otherwise(pl.lit(DocTypeCanonical.OTHER.value))
            .alias("doc_type_canonical"),
            amounts.alias("amount"),
            pl.col("grantees").cast(pl.Utf8).alias("grantee_name_raw"),
            grantors.alias("grantor_name_raw"),
            parcels.alias("parcel_id"),
            pl.lit(SOURCE_DATASET).alias("source_dataset"),
        )
        self.filter_counts.append(FilterCount("rtt_to_transfers", "loaded", rows_in, result.height))
        return result
