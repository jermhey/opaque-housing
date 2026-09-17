"""NY Department of State active corporations.

Field names were verified against data.ny.gov n9v6-gdp6 on 2026-09-17.
See docs/data_sources.md. Inactive/dissolved entities are not in this table.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.classify.pipeline import classify_owner
from opaque_housing.normalize.addresses import address_key, is_care_of, normalize_address
from opaque_housing.normalize.batch import attach_normalized_name
from opaque_housing.normalize.names import normalize_name
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import OwnerClass

SOURCE_DATASET = "nys_dos"
SOURCE_VERSION = "open-ny-2026-09-17"

REQUIRED = ("dos_id", "current_entity_name")


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported DOS extract suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.lower() for name in df.columns})


def _fill(df: pl.DataFrame, name: str) -> pl.Expr:
    if name in df.columns:
        return pl.col(name).cast(pl.Utf8).fill_null("")
    return pl.lit("")


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


class NycDosAdapter:
    metro_id = "nyc"

    def __init__(self, source_version: str = SOURCE_VERSION) -> None:
        self.source_version = source_version
        self.filter_counts: list[FilterCount] = []

    def load_entities(
        self, path: Path, owner_keys: pl.DataFrame | None = None
    ) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(path))
        missing = [col for col in REQUIRED if col not in raw.columns]
        if missing:
            raise ValueError(f"nys dos extract missing required columns: {missing}")
        rows_in = raw.height
        work = raw.with_columns(
            _fill(raw, "dos_id").alias("entity_id"),
            _fill(raw, "current_entity_name").alias("current_entity_name"),
            _fill(raw, "initial_dos_filing_date").alias("initial_dos_filing_date"),
            _fill(raw, "county").alias("county"),
            _fill(raw, "jurisdiction").alias("jurisdiction"),
            _fill(raw, "entity_type").alias("entity_type"),
            _fill(raw, "dos_process_name").alias("dos_process_name"),
            _fill(raw, "dos_process_address_1").alias("dos_process_address_1"),
            _fill(raw, "dos_process_address_2").alias("dos_process_address_2"),
            _fill(raw, "dos_process_city").alias("dos_process_city"),
            _fill(raw, "dos_process_state").alias("dos_process_state"),
            _fill(raw, "dos_process_zip").alias("dos_process_zip"),
            _fill(raw, "chairman_name").alias("chairman_name"),
            _fill(raw, "registered_agent_name").alias("registered_agent_name"),
            _fill(raw, "registered_agent_address_1").alias("registered_agent_address_1"),
            _fill(raw, "registered_agent_city").alias("registered_agent_city"),
            _fill(raw, "registered_agent_state").alias("registered_agent_state"),
            _fill(raw, "registered_agent_zip").alias("registered_agent_zip"),
        )
        named = attach_normalized_name(work, "current_entity_name")
        self.filter_counts.append(FilterCount("nys_dos", "loaded", rows_in, named.height))
        if owner_keys is not None:
            named = self.match_owners(named, owner_keys)
        return self._enrich(named)

    def _enrich(self, work: pl.DataFrame) -> pl.DataFrame:
        if work.is_empty():
            return work
        process_addr = [
            normalize_address(
                rec["dos_process_address_1"],
                rec["dos_process_address_2"],
                rec["dos_process_city"],
                rec["dos_process_state"],
                rec["dos_process_zip"],
            )
            for rec in work.select(
                [
                    "dos_process_address_1",
                    "dos_process_address_2",
                    "dos_process_city",
                    "dos_process_state",
                    "dos_process_zip",
                ]
            ).iter_rows(named=True)
        ]
        process_co = [
            is_care_of(rec["dos_process_name"], rec["dos_process_address_1"])
            for rec in work.select(["dos_process_name", "dos_process_address_1"]).iter_rows(
                named=True
            )
        ]
        formation = [_parse_date(value) for value in work["initial_dos_filing_date"].to_list()]
        return work.with_columns(
            pl.Series("process_address_normalized", process_addr),
            pl.Series("process_is_care_of", process_co),
            pl.Series("formation_date", formation),
            pl.col("dos_process_name")
            .map_elements(normalize_name, return_dtype=pl.Utf8)
            .alias("process_name_normalized"),
            pl.col("registered_agent_name")
            .map_elements(normalize_name, return_dtype=pl.Utf8)
            .alias("registered_agent_name_normalized"),
            pl.col("chairman_name")
            .map_elements(normalize_name, return_dtype=pl.Utf8)
            .alias("chairman_name_normalized"),
        ).with_columns(
            pl.col("process_address_normalized")
            .map_elements(address_key, return_dtype=pl.Utf8)
            .alias("process_address_key"),
        )

    def match_owners(self, entities: pl.DataFrame, owner_keys: pl.DataFrame) -> pl.DataFrame:
        """Keep DOS rows whose normalized entity name is an owner_key we care about."""
        rows_in = entities.height
        if entities.is_empty() or owner_keys.is_empty():
            self.filter_counts.append(FilterCount("nys_dos", "name_match", rows_in, 0))
            return entities.head(0)
        keys = owner_keys.select("owner_key").unique()
        matched = entities.join(keys, on="owner_key", how="inner")
        self.filter_counts.append(
            FilterCount("nys_dos", "name_match", rows_in, matched.height)
        )
        return matched


def chairman_is_person(chairman_name_normalized: str) -> bool:
    if not chairman_name_normalized:
        return False
    return classify_owner(chairman_name_normalized).owner_class is OwnerClass.INDIVIDUAL


def process_name_is_other_entity(process_name_normalized: str, owner_name_normalized: str) -> bool:
    if not process_name_normalized or process_name_normalized == owner_name_normalized:
        return False
    owner = classify_owner(process_name_normalized)
    return owner.owner_class in {OwnerClass.LLC, OwnerClass.CORP, OwnerClass.PARTNERSHIP}
