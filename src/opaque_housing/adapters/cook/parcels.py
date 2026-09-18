"""Cook County universe + addresses → canonical parcels_snapshot.

Field names were verified against live Assessor SODA on 2026-09-18.
See docs/data_sources.md and ADR 0013.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.cook.building_type import (
    building_type_and_units,
    is_residential,
    normalize_class,
)
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import ParcelSnapshot

SOURCE_DATASET = "cook_assessor"


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported Cook extract suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.lower() for name in df.columns})


def format_pin(value: object) -> str:
    if value is None or value == "":
        return ""
    text = str(value).strip()
    if "." in text and text.replace(".", "", 1).isdigit():
        text = text.split(".", 1)[0]
    return text.zfill(14)


def _series_or_empty(frame: pl.DataFrame, name: str) -> list[object]:
    if name in frame.columns:
        return frame[name].to_list()
    return [None] * frame.height


class CookParcelAdapter:
    metro_id = "cook"

    def __init__(self, snapshot_date: date) -> None:
        self.snapshot_date = snapshot_date
        self.filter_counts: list[FilterCount] = []

    def load_parcels_snapshot(
        self,
        universe_path: Path,
        *,
        addresses_path: Path | None = None,
        characteristics_path: Path | None = None,
        condo_path: Path | None = None,
    ) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(universe_path))
        if "pin" not in raw.columns or "class" not in raw.columns:
            raise ValueError("Cook universe extract missing pin/class")
        rows_in = raw.height
        raw = raw.with_columns(
            pl.col("pin").map_elements(format_pin, return_dtype=pl.Utf8).alias("parcel_id"),
            pl.col("class").map_elements(normalize_class, return_dtype=pl.Utf8).alias("class_norm"),
        )
        kept = raw.filter(
            pl.Series("keep", [is_residential(code) for code in raw["class_norm"].to_list()])
        )
        if addresses_path is not None and addresses_path.exists():
            addr = _normalize_columns(_read_table(addresses_path)).with_columns(
                pl.col("pin").map_elements(format_pin, return_dtype=pl.Utf8).alias("parcel_id")
            )
            owner = (
                pl.col("owner_address_name").cast(pl.Utf8)
                if "owner_address_name" in addr.columns
                else pl.lit("")
            )
            mail = (
                pl.col("mail_address_name").cast(pl.Utf8)
                if "mail_address_name" in addr.columns
                else pl.lit("")
            )
            mailing = (
                pl.col("owner_address_full").cast(pl.Utf8)
                if "owner_address_full" in addr.columns
                else pl.lit(None)
            )
            addr = (
                addr.with_columns(
                    owner.alias("owner_name_join"),
                    mail.alias("mail_name_join"),
                    mailing.alias("owner_mailing_address_raw"),
                )
                .sort("parcel_id")
                .unique(subset=["parcel_id"], keep="last")
                .select(
                    "parcel_id",
                    "owner_name_join",
                    "mail_name_join",
                    "owner_mailing_address_raw",
                )
            )
            kept = kept.join(addr, on="parcel_id", how="left")
        else:
            kept = kept.with_columns(
                pl.lit(None).cast(pl.Utf8).alias("owner_name_join"),
                pl.lit(None).cast(pl.Utf8).alias("mail_name_join"),
                pl.lit(None).cast(pl.Utf8).alias("owner_mailing_address_raw"),
            )
        if characteristics_path is not None and characteristics_path.exists():
            chars = _normalize_columns(_read_table(characteristics_path)).with_columns(
                pl.col("pin").map_elements(format_pin, return_dtype=pl.Utf8).alias("parcel_id")
            )
            apts = (
                chars["char_apts"].cast(pl.Utf8)
                if "char_apts" in chars.columns
                else pl.lit(None).cast(pl.Utf8)
            )
            chars = (
                chars.with_columns(apts.alias("char_apts"))
                .sort("parcel_id")
                .unique(subset=["parcel_id"], keep="last")
                .select("parcel_id", "char_apts")
            )
            kept = kept.join(chars, on="parcel_id", how="left")
        else:
            kept = kept.with_columns(pl.lit(None).cast(pl.Utf8).alias("char_apts"))
        if condo_path is not None and condo_path.exists():
            condo = _normalize_columns(_read_table(condo_path)).with_columns(
                pl.col("pin").map_elements(format_pin, return_dtype=pl.Utf8).alias("parcel_id")
            )
            parking = (
                condo["is_parking_space"] if "is_parking_space" in condo.columns else pl.lit(False)
            )
            common = condo["is_common_area"] if "is_common_area" in condo.columns else pl.lit(False)
            condo = (
                condo.with_columns(
                    parking.alias("is_parking_space"),
                    common.alias("is_common_area"),
                )
                .sort("parcel_id")
                .unique(subset=["parcel_id"], keep="last")
                .select("parcel_id", "is_parking_space", "is_common_area")
            )
            kept = kept.join(condo, on="parcel_id", how="left")
        else:
            kept = kept.with_columns(
                pl.lit(False).alias("is_parking_space"),
                pl.lit(False).alias("is_common_area"),
            )

        types: list[str] = []
        units: list[int] = []
        keep_mask: list[bool] = []
        for row in kept.iter_rows(named=True):
            mapped = building_type_and_units(
                row.get("class_norm"),
                char_apts=row.get("char_apts"),
                parking=row.get("is_parking_space"),
                common_area=row.get("is_common_area"),
            )
            if mapped is None:
                keep_mask.append(False)
                types.append("")
                units.append(0)
                continue
            keep_mask.append(True)
            types.append(mapped[0].value)
            units.append(mapped[1])
        kept = kept.with_columns(
            pl.Series("keep_type", keep_mask),
            pl.Series("building_type", types, dtype=pl.Utf8),
            pl.Series("res_units", units, dtype=pl.Int64),
        ).filter(pl.col("keep_type"))

        townships = [str(value or "").strip() for value in _series_or_empty(kept, "township_name")]
        nbhds = [str(value or "").strip() for value in _series_or_empty(kept, "nbhd_code")]
        neighborhoods = [
            f"{town} {nbhd}".strip() if town or nbhd else ""
            for town, nbhd in zip(townships, nbhds, strict=True)
        ]
        tracts = []
        for value in _series_or_empty(kept, "census_tract_geoid"):
            text = str(value or "").strip()
            tracts.append(text if len(text) >= 11 else None)
        owners = []
        for row in kept.iter_rows(named=True):
            primary = str(row.get("owner_name_join") or "").strip()
            fallback = str(row.get("mail_name_join") or "").strip()
            owners.append(primary or fallback or None)
        versions = [str(self.snapshot_date.year)] * kept.height
        result = kept.with_columns(
            pl.lit(self.metro_id).alias("metro_id"),
            pl.lit(self.snapshot_date).alias("snapshot_date"),
            pl.Series("geo_tract", tracts, dtype=pl.Utf8),
            pl.Series("geo_neighborhood", neighborhoods, dtype=pl.Utf8),
            pl.Series("geo_borough", townships, dtype=pl.Utf8),
            pl.Series("owner_name_raw", owners, dtype=pl.Utf8),
            pl.col("owner_mailing_address_raw").cast(pl.Utf8),
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
                stage="cook_to_parcels",
                rule_id="cook_residential_only",
                rows_in=rows_in,
                rows_out=result.height,
            )
        )
        return result


def parcels_from_frame(df: pl.DataFrame) -> list[ParcelSnapshot]:
    return [ParcelSnapshot.model_validate(row) for row in df.iter_rows(named=True)]
