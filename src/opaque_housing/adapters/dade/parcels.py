"""Miami-Dade PaGis folios → canonical parcels_snapshot.

Field names were verified against live MapServer/24 on 2026-09-18.
See ADR 0014.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.dade.building_type import (
    building_type_and_units,
    is_residential,
)
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import ParcelSnapshot

SOURCE_DATASET = "dade_pagis"


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported Dade extract suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.upper() if name.isascii() else name for name in df.columns})


def format_folio(value: object) -> str:
    if value is None or value == "":
        return ""
    text = str(value).strip()
    if "." in text and text.replace(".", "", 1).isdigit():
        text = text.split(".", 1)[0]
    return text


class DadeParcelAdapter:
    metro_id = "dade"

    def __init__(self, snapshot_date: date) -> None:
        self.snapshot_date = snapshot_date
        self.filter_counts: list[FilterCount] = []

    def load_parcels_snapshot(self, source_path: Path) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(source_path))
        required = ("FOLIO", "TRUE_OWNER1")
        missing = [col for col in required if col not in raw.columns]
        if missing:
            raise ValueError(f"Dade GIS extract missing required columns: {missing}")
        rows_in = raw.height
        descriptions = raw["DOR_DESC"].to_list() if "DOR_DESC" in raw.columns else [""] * raw.height
        cancels = (
            raw["CANCEL_FLAG"].to_list() if "CANCEL_FLAG" in raw.columns else [None] * raw.height
        )
        keep_mask = [
            is_residential(description, flag)
            for description, flag in zip(descriptions, cancels, strict=True)
        ]
        kept = raw.filter(pl.Series("keep", keep_mask))
        types: list[str] = []
        units: list[int] = []
        desc_col = kept["DOR_DESC"].to_list() if "DOR_DESC" in kept.columns else [""] * kept.height
        unit_col = (
            kept["UNIT_COUNT"].to_list() if "UNIT_COUNT" in kept.columns else [None] * kept.height
        )
        for description, count in zip(desc_col, unit_col, strict=True):
            btype, n_units = building_type_and_units(description, count)
            types.append(btype.value)
            units.append(n_units)
        cities = (
            kept["TRUE_SITE_CITY"].cast(pl.Utf8).fill_null("").str.strip_chars().to_list()
            if "TRUE_SITE_CITY" in kept.columns
            else [""] * kept.height
        )
        zips = (
            kept["TRUE_SITE_ZIP_CODE"].cast(pl.Utf8).fill_null("").str.slice(0, 5).to_list()
            if "TRUE_SITE_ZIP_CODE" in kept.columns
            else [""] * kept.height
        )
        mail = (
            kept["TRUE_MAILING_ADDR1"].cast(pl.Utf8).to_list()
            if "TRUE_MAILING_ADDR1" in kept.columns
            else [None] * kept.height
        )
        if "ASSESSMENT_YEAR_CUR" in kept.columns:
            versions = [
                str(value or self.snapshot_date.year)
                for value in kept["ASSESSMENT_YEAR_CUR"].to_list()
            ]
        else:
            versions = [str(self.snapshot_date.year)] * kept.height
        result = kept.with_columns(
            pl.lit(self.metro_id).alias("metro_id"),
            pl.col("FOLIO").map_elements(format_folio, return_dtype=pl.Utf8).alias("parcel_id"),
            pl.lit(self.snapshot_date).alias("snapshot_date"),
            pl.lit(None).cast(pl.Utf8).alias("geo_tract"),
            pl.Series("geo_neighborhood", zips, dtype=pl.Utf8),
            pl.Series("geo_borough", cities, dtype=pl.Utf8),
            pl.Series("building_type", types, dtype=pl.Utf8),
            pl.Series("res_units", units, dtype=pl.Int64),
            pl.col("TRUE_OWNER1").cast(pl.Utf8).alias("owner_name_raw"),
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
                stage="dade_to_parcels",
                rule_id="dade_residential_only",
                rows_in=rows_in,
                rows_out=result.height,
            )
        )
        return result


def parcels_from_frame(df: pl.DataFrame) -> list[ParcelSnapshot]:
    return [ParcelSnapshot.model_validate(row) for row in df.iter_rows(named=True)]
