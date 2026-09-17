"""NYC PLUTO → canonical parcels_snapshot.

Field names were verified against NYC Open Data 64uk-42ks (PLUTO 26v2)
on 2026-09-16. See docs/data_sources.md.
"""

from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.building_type import (
    building_type_from_pluto,
    is_residential_pluto,
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
                key = str(row.get("boroct2020") or "")
                nta = row.get("ntacode") or row.get("nta2020")
                if key and nta:
                    nta_by_bct[key] = str(nta)

        records: list[dict[str, object]] = []
        rows_in = raw.height
        for row in raw.iter_rows(named=True):
            if not is_residential_pluto(
                bldgclass=row["bldgclass"],
                landuse=row.get("landuse"),
                unitsres=row["unitsres"],
            ):
                continue
            bct = "" if row["bct2020"] is None else str(row["bct2020"]).strip()
            records.append(
                {
                    "metro_id": self.metro_id,
                    "parcel_id": format_bbl(row["bbl"]),
                    "snapshot_date": self.snapshot_date,
                    "geo_tract": format_geoid(row["borocode"], row["bct2020"], self._county_fips),
                    "geo_neighborhood": nta_by_bct.get(bct),
                    "building_type": building_type_from_pluto(
                        bldgclass=row["bldgclass"],
                        landuse=row.get("landuse"),
                        unitsres=row["unitsres"],
                    ).value,
                    "res_units": int(float(str(row["unitsres"] or 0))),
                    "owner_name_raw": None if row["ownername"] is None else str(row["ownername"]),
                    "owner_mailing_address_raw": None,
                    "source_dataset": SOURCE_DATASET,
                    "source_version": "" if row["version"] is None else str(row["version"]),
                }
            )
        self.filter_counts.append(
            FilterCount(
                stage="pluto_to_parcels",
                rule_id="pluto_residential_only",
                rows_in=rows_in,
                rows_out=len(records),
            )
        )
        return pl.DataFrame(records)


def parcels_from_frame(df: pl.DataFrame) -> list[ParcelSnapshot]:
    return [ParcelSnapshot.model_validate(row) for row in df.iter_rows(named=True)]
