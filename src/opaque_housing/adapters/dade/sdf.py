"""Florida DOR Sale Data File → canonical transfers.

Field names and order are from the 2024/2025 DOR SDF user's guide (Section 2).
Production files have no header. There is no buyer name (ADR 0014).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.dade.parcels import format_folio
from opaque_housing.adapters.dade.sources import DADE_COUNTY_NO, SDF_FIELDS
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import DocTypeCanonical

SOURCE_DATASET = "dade_sdf"
SOURCE_VERSION = "florida-sdf-2026-09-18"
QUALIFIED = frozenset({"01", "1"})


def _read_sdf(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix not in {".csv", ".tsv"}:
        raise ValueError(f"unsupported SDF suffix: {suffix}")
    headered = pl.read_csv(path, infer_schema_length=0, n_rows=1)
    names = {name.upper() for name in headered.columns}
    if "PARCEL_ID" in names or "CO_NO" in names:
        return pl.read_csv(path, infer_schema_length=0)
    return pl.read_csv(
        path,
        has_header=False,
        new_columns=list(SDF_FIELDS[: len(headered.columns)] or SDF_FIELDS),
        infer_schema_length=0,
    )


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.upper() for name in df.columns})


def _sale_date(year: object, month: object) -> date | None:
    try:
        yr = int(float(str(year)))
        mo = int(float(str(month or "1")))
    except (TypeError, ValueError):
        return None
    if yr < 1800 or not 1 <= mo <= 12:
        return None
    return date(yr, mo, 1)


class DadeSdfAdapter:
    metro_id = "dade"

    def __init__(self, source_version: str = SOURCE_VERSION) -> None:
        self.source_version = source_version
        self.filter_counts: list[FilterCount] = []

    def load_transfers(self, source_path: Path) -> pl.DataFrame:
        raw = _normalize_columns(_read_sdf(source_path))
        if "PARCEL_ID" not in raw.columns:
            raise ValueError("SDF extract missing PARCEL_ID")
        rows_in = raw.height
        if "CO_NO" in raw.columns:
            county = raw["CO_NO"].cast(pl.Utf8).str.strip_chars().str.replace(r"\.0$", "")
            raw = raw.filter(county.is_in([DADE_COUNTY_NO, DADE_COUNTY_NO.lstrip("0") or "23"]))
        clerk = raw["CLERK_NO"].cast(pl.Utf8) if "CLERK_NO" in raw.columns else pl.lit("")
        book = raw["OR_BOOK"].cast(pl.Utf8) if "OR_BOOK" in raw.columns else pl.lit("")
        page = raw["OR_PAGE"].cast(pl.Utf8) if "OR_PAGE" in raw.columns else pl.lit("")
        sale_id = raw["SALE_ID_CD"].cast(pl.Utf8) if "SALE_ID_CD" in raw.columns else pl.lit("")
        qual = raw["QUAL_CD"].cast(pl.Utf8) if "QUAL_CD" in raw.columns else pl.lit("")
        years = raw["SALE_YR"].to_list() if "SALE_YR" in raw.columns else [None] * raw.height
        months = raw["SALE_MO"].to_list() if "SALE_MO" in raw.columns else [None] * raw.height
        dates = [_sale_date(year, month) for year, month in zip(years, months, strict=True)]
        amount = (
            raw["SALE_PRC"].cast(pl.Float64, strict=False)
            if "SALE_PRC" in raw.columns
            else pl.lit(None)
        )
        typed = raw.with_columns(
            clerk.alias("clerk_no"),
            book.alias("or_book"),
            page.alias("or_page"),
            sale_id.alias("sale_id"),
            qual.str.strip_chars().str.replace(r"\.0$", "").alias("doc_type_raw"),
            amount.alias("consideration"),
            pl.col("PARCEL_ID").map_elements(format_folio, return_dtype=pl.Utf8).alias("parcel_id"),
            pl.Series("recorded_date", dates, dtype=pl.Date),
        ).with_columns(
            pl.coalesce(
                pl.when(pl.col("clerk_no").fill_null("") != "").then(pl.col("clerk_no")),
                pl.when(
                    (pl.col("or_book").fill_null("") != "")
                    & (pl.col("or_page").fill_null("") != "")
                ).then(pl.concat_str([pl.col("or_book"), pl.lit("-"), pl.col("or_page")])),
                pl.when(pl.col("sale_id").fill_null("") != "").then(pl.col("sale_id")),
                pl.col("parcel_id"),
            ).alias("doc_id"),
            pl.when(pl.col("doc_type_raw").is_in(list(QUALIFIED)))
            .then(pl.lit(DocTypeCanonical.SALE_DEED.value))
            .otherwise(pl.lit(DocTypeCanonical.OTHER.value))
            .alias("doc_type_canonical"),
        )
        result = (
            typed.group_by("doc_id", maintain_order=True)
            .agg(
                pl.col("recorded_date").first(),
                pl.col("recorded_date").first().alias("doc_date"),
                pl.col("doc_type_raw").first(),
                pl.col("doc_type_canonical").first(),
                pl.col("consideration").first(),
                pl.col("parcel_id")
                .filter(pl.col("parcel_id") != "")
                .unique(maintain_order=True)
                .alias("parcel_ids"),
            )
            .with_columns(
                pl.lit(self.metro_id).alias("metro_id"),
                pl.lit(None).cast(pl.Float64).alias("percent_trans"),
                pl.lit(None).cast(pl.Utf8).alias("grantee_name_raw"),
                pl.lit(None).cast(pl.Utf8).alias("grantor_name_raw"),
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
                stage="dade_sdf_to_transfers",
                rule_id="group_document_parcels",
                rows_in=rows_in,
                rows_out=result.height,
            )
        )
        return result
