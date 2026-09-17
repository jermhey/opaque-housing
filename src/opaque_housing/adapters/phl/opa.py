"""Philadelphia OPA → canonical parcels_snapshot.

Field names were verified against live ``opa_properties_public`` on 2026-09-17.
See docs/data_sources.md and ADR 0010.
"""

from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.phl.building_type import (
    building_type_and_units,
    is_residential,
)
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import ParcelSnapshot

SOURCE_DATASET = "phl_opa"


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported OPA extract suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.lower() for name in df.columns})


def format_parcel_number(value: object) -> str:
    if value is None or value == "":
        return ""
    text = str(value).strip()
    if "." in text:
        text = text.split(".", 1)[0]
    return text.zfill(9)


def mailing_address(row: dict[str, object]) -> str | None:
    parts = [
        str(row.get("mailing_street") or row.get("mailing_address_1") or "").strip(),
        str(row.get("mailing_city_state") or "").strip(),
        str(row.get("mailing_zip") or "").strip(),
    ]
    text = ", ".join(part for part in parts if part)
    return text or None


class PhlOpaAdapter:
    metro_id = "phl"

    def __init__(self, snapshot_date: date) -> None:
        self.snapshot_date = snapshot_date
        self.filter_counts: list[FilterCount] = []

    def load_parcels_snapshot(self, source_path: Path) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(source_path))
        required = ("parcel_number", "owner_1", "category_code")
        missing = [col for col in required if col not in raw.columns]
        if missing:
            raise ValueError(f"OPA extract missing required columns: {missing}")
        rows_in = raw.height
        keep_mask = [
            is_residential(cat, desc)
            for cat, desc in zip(
                raw["category_code"].to_list(),
                raw["building_code_description"].to_list()
                if "building_code_description" in raw.columns
                else [None] * raw.height,
                strict=True,
            )
        ]
        kept = raw.filter(pl.Series("keep", keep_mask))
        types: list[str] = []
        units: list[int] = []
        desc_col = (
            kept["building_code_description"].to_list()
            if "building_code_description" in kept.columns
            else [None] * kept.height
        )
        for cat, desc in zip(kept["category_code"].to_list(), desc_col, strict=True):
            btype, n_units = building_type_and_units(cat, desc)
            types.append(btype.value)
            units.append(n_units)
        zips = (
            kept["zip_code"].cast(pl.Utf8).fill_null("").str.slice(0, 5).to_list()
            if "zip_code" in kept.columns
            else [""] * kept.height
        )
        mail = [mailing_address(row) for row in kept.iter_rows(named=True)]
        if "assessment_date" in kept.columns:
            dated = kept["assessment_date"].cast(pl.Utf8).fill_null("").str.slice(0, 10)
            latest = max((value for value in dated.to_list() if value), default="")
            versions = [latest] * kept.height
        else:
            versions = [""] * kept.height
        result = kept.with_columns(
            pl.lit(self.metro_id).alias("metro_id"),
            pl.col("parcel_number")
            .map_elements(format_parcel_number, return_dtype=pl.Utf8)
            .alias("parcel_id"),
            pl.lit(self.snapshot_date).alias("snapshot_date"),
            pl.lit(None).cast(pl.Utf8).alias("geo_tract"),
            pl.Series("geo_neighborhood", zips, dtype=pl.Utf8),
            pl.lit("Philadelphia").alias("geo_borough"),
            pl.Series("building_type", types, dtype=pl.Utf8),
            pl.Series("res_units", units, dtype=pl.Int64),
            pl.col("owner_1").cast(pl.Utf8).alias("owner_name_raw"),
            pl.Series("owner_mailing_address_raw", mail, dtype=pl.Utf8),
            pl.lit(SOURCE_DATASET).alias("source_dataset"),
            pl.Series("source_version", versions, dtype=pl.Utf8),
        ).select(
            "metro_id",
            "parcel_id",
            "snapshot_date",
            "geo_tract",
            "geo_neighborhood",
            "geo_borough",
            "building_type",
            "res_units",
            "owner_name_raw",
            "owner_mailing_address_raw",
            "source_dataset",
            "source_version",
        )
        self.filter_counts.append(
            FilterCount(
                stage="opa_to_parcels",
                rule_id="opa_residential_only",
                rows_in=rows_in,
                rows_out=result.height,
            )
        )
        return result


def parcels_from_frame(df: pl.DataFrame) -> list[ParcelSnapshot]:
    return [ParcelSnapshot.model_validate(row) for row in df.iter_rows(named=True)]
