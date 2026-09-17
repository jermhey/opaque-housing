"""NYC PLUTO → canonical parcels_snapshot.

Field names were verified against NYC Open Data 64uk-42ks (PLUTO 26v2)
on 2026-09-16. See docs/data_sources.md.
"""

from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.building_type import (
    building_type_expr,
    building_type_from_pluto,
    residential_expr,
)
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import ParcelSnapshot

LOOKUP_DIR = Path(__file__).parent / "lookups"
BORO_FIPS_PATH = LOOKUP_DIR / "nyc_boro_county_fips.csv"

REQUIRED_COLUMNS = (
    "bbl",
    "bldgclass",
    "unitsres",
    "ownername",
    "version",
    "bct2020",
    "borocode",
)

SOURCE_DATASET = "nyc_pluto"


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported PLUTO extract suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.lower() for name in df.columns})


def format_bbl(value: object) -> str:
    if value is None or value == "":
        return ""
    text = str(value).strip()
    if "." in text:
        text = text.split(".", 1)[0]
    if text.endswith("e+09") or "e" in text.lower():
        text = str(int(float(str(value))))
    return text.zfill(10)


def format_geoid(borocode: object, bct2020: object, county_fips: dict[str, str]) -> str | None:
    if borocode is None or bct2020 is None or bct2020 == "":
        return None
    boro = str(int(float(str(borocode))))
    fips = county_fips.get(boro)
    tract = str(bct2020).strip()
    if tract.startswith(boro) and len(tract) >= 7:
        tract = tract[len(boro) :]
    tract = tract.replace(".", "").zfill(6)
    if fips is None:
        return None
    return f"36{fips}{tract}"


def load_boro_county_fips(path: Path = BORO_FIPS_PATH) -> dict[str, str]:
    table = pl.read_csv(path, infer_schema_length=0)
    return {
        row["borocode"].lstrip("0") or "0": row["countyfips"] for row in table.iter_rows(named=True)
    }


def _bct_key(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if "." in text:
        text = text.split(".", 1)[0]
    return text


class NycPlutoAdapter:
    metro_id = "nyc"

    def __init__(self, snapshot_date: date, tract_equiv_path: Path | None = None) -> None:
        self.snapshot_date = snapshot_date
        self.tract_equiv_path = tract_equiv_path
        self.filter_counts: list[FilterCount] = []
        self._county_fips = load_boro_county_fips()

    def load_parcels_snapshot(self, source_path: Path) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(source_path))
        missing = [col for col in REQUIRED_COLUMNS if col not in raw.columns]
        if missing:
            raise ValueError(f"PLUTO extract missing required columns: {missing}")

        nta_by_bct: dict[str, str] = {}
        if self.tract_equiv_path is not None:
            equiv = _normalize_columns(_read_table(self.tract_equiv_path))
            for row in equiv.iter_rows(named=True):
                key = _bct_key(row.get("boroct2020"))
                nta = row.get("ntacode") or row.get("nta2020")
                if key and nta:
                    nta_by_bct[key] = str(nta)

        rows_in = raw.height
        kept = raw.filter(residential_expr())
        geo_tracts = [
            format_geoid(boro, tract, self._county_fips)
            for boro, tract in zip(
                kept["borocode"].to_list(),
                kept["bct2020"].to_list(),
                strict=True,
            )
        ]
        geo_neighborhoods = [_bct_key(value) for value in kept["bct2020"].to_list()]
        geo_neighborhoods = [nta_by_bct.get(key) for key in geo_neighborhoods]
        result = kept.with_columns(
            pl.lit(self.metro_id).alias("metro_id"),
            pl.col("bbl").map_elements(format_bbl, return_dtype=pl.Utf8).alias("parcel_id"),
            pl.lit(self.snapshot_date).alias("snapshot_date"),
            pl.Series("geo_tract", geo_tracts, dtype=pl.Utf8),
            pl.Series("geo_neighborhood", geo_neighborhoods, dtype=pl.Utf8),
            building_type_expr().alias("building_type"),
            _units_int_expr().alias("res_units"),
            pl.col("ownername").cast(pl.Utf8).alias("owner_name_raw"),
            pl.lit(None).cast(pl.Utf8).alias("owner_mailing_address_raw"),
            pl.lit(SOURCE_DATASET).alias("source_dataset"),
            pl.col("version").cast(pl.Utf8).fill_null("").alias("source_version"),
        ).select(
            "metro_id",
            "parcel_id",
            "snapshot_date",
            "geo_tract",
            "geo_neighborhood",
            "building_type",
            "res_units",
            "owner_name_raw",
            "owner_mailing_address_raw",
            "source_dataset",
            "source_version",
        )
        self.filter_counts.append(
            FilterCount(
                stage="pluto_to_parcels",
                rule_id="pluto_residential_only",
                rows_in=rows_in,
                rows_out=result.height,
            )
        )
        return result


def _units_int_expr() -> pl.Expr:
    return pl.col("unitsres").cast(pl.Float64, strict=False).fill_null(0).cast(pl.Int64)


def parcels_from_frame(df: pl.DataFrame) -> list[ParcelSnapshot]:
    return [ParcelSnapshot.model_validate(row) for row in df.iter_rows(named=True)]


# Re-export so existing tests that imported the Python mapper still work.
__all__ = [
    "NycPlutoAdapter",
    "SOURCE_DATASET",
    "building_type_from_pluto",
    "format_bbl",
    "format_geoid",
    "load_boro_county_fips",
    "parcels_from_frame",
]
