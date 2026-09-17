"""NYC ACRIS Master / Legals / Parties → canonical transfers.

Field names were verified against NYC Open Data bnx9-e6tj, 8h5j-fqxa, and
636b-3b5g on 2026-09-16/17. See docs/data_sources.md and ADR 0005 / 0006.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.bbl import format_bbl_parts
from opaque_housing.adapters.nyc.doc_types import canonical_doc_type_expr
from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import PartyRole, Transfer, TransferParty

SOURCE_DATASET = "nyc_acris"
SOURCE_VERSION = "open-data-2026-09-17"

MASTER_REQUIRED = (
    "document_id",
    "doc_type",
    "document_amt",
    "recorded_datetime",
)
LEGAL_REQUIRED = ("document_id", "borough", "block", "lot")
PARTY_REQUIRED = ("document_id", "party_type", "name")


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported ACRIS extract suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.lower() for name in df.columns})


def _parse_date_expr(column: str) -> pl.Expr:
    text = pl.col(column).cast(pl.Utf8)
    parsed = pl.coalesce(
        text.str.strptime(pl.Date, "%Y-%m-%dT%H:%M:%S%.f", strict=False),
        text.str.strptime(pl.Date, "%Y-%m-%dT%H:%M:%S", strict=False),
        text.str.strptime(pl.Date, "%Y-%m-%d", strict=False),
    )
    return pl.when(parsed.dt.year() < 1800).then(None).otherwise(parsed)


def latest_snapshot(df: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Keep the latest good_through_date per key grain (ADR 0006)."""
    if df.is_empty():
        return df
    work = df
    if "good_through_date" not in work.columns:
        work = work.with_columns(pl.lit("").alias("good_through_date"))
    return work.sort("good_through_date").group_by(keys, maintain_order=True).last()


def _require(df: pl.DataFrame, required: tuple[str, ...], label: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{label} extract missing required columns: {missing}")


class NycAcrisAdapter:
    metro_id = "nyc"

    def __init__(self, source_version: str = SOURCE_VERSION) -> None:
        self.source_version = source_version
        self.filter_counts: list[FilterCount] = []

    def load_transfers(self, master_path: Path, legals_path: Path) -> pl.DataFrame:
        master = _normalize_columns(_read_table(master_path))
        legals = _normalize_columns(_read_table(legals_path))
        _require(master, MASTER_REQUIRED, "ACRIS Master")
        _require(legals, LEGAL_REQUIRED, "ACRIS Legals")

        master_in = master.height
        master = latest_snapshot(master, ["document_id"])
        self.filter_counts.append(
            FilterCount(
                stage="acris_master",
                rule_id="snapshot_dedup_document_id",
                rows_in=master_in,
                rows_out=master.height,
            )
        )

        legal_keys = ["document_id", "borough", "block", "lot"]
        legal_in = legals.height
        legals = latest_snapshot(legals, legal_keys)
        self.filter_counts.append(
            FilterCount(
                stage="acris_legals",
                rule_id="snapshot_dedup_document_lot",
                rows_in=legal_in,
                rows_out=legals.height,
            )
        )

        parcel_ids = [
            format_bbl_parts(row["borough"], row["block"], row["lot"])
            for row in legals.select(["borough", "block", "lot"]).iter_rows(named=True)
        ]
        lots = (
            legals.with_columns(pl.Series("parcel_id", parcel_ids, dtype=pl.Utf8))
            .filter(pl.col("parcel_id") != "")
            .group_by("document_id")
            .agg(pl.col("parcel_id").unique(maintain_order=True).alias("parcel_ids"))
        )

        amount = pl.col("document_amt").cast(pl.Float64, strict=False)
        percent = (
            pl.col("percent_trans").cast(pl.Float64, strict=False)
            if "percent_trans" in master.columns
            else pl.lit(None).cast(pl.Float64)
        )
        doc_date_col = (
            _parse_date_expr("document_date")
            if "document_date" in master.columns
            else pl.lit(None).cast(pl.Date)
        )
        transfers = (
            master.with_columns(
                pl.lit(self.metro_id).alias("metro_id"),
                pl.col("document_id").cast(pl.Utf8).alias("doc_id"),
                _parse_date_expr("recorded_datetime").alias("recorded_date"),
                doc_date_col.alias("doc_date"),
                pl.col("doc_type").cast(pl.Utf8).str.strip_chars().alias("doc_type_raw"),
                canonical_doc_type_expr("doc_type").alias("doc_type_canonical"),
                amount.alias("consideration"),
                percent.alias("percent_trans"),
                pl.lit(SOURCE_DATASET).alias("source_dataset"),
                pl.lit(self.source_version).alias("source_version"),
            )
            .join(lots, left_on="doc_id", right_on="document_id", how="left")
            .with_columns(pl.col("parcel_ids").fill_null(pl.lit([], dtype=pl.List(pl.Utf8))))
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
                "source_dataset",
                "source_version",
            )
        )
        return transfers

    def load_transfer_parties(self, parties_path: Path) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(parties_path))
        _require(raw, PARTY_REQUIRED, "ACRIS Parties")
        rows_in = raw.height
        grain = ["document_id", "party_type", "name"]
        if "address_1" in raw.columns:
            grain.append("address_1")
        deduped = latest_snapshot(raw, grain)
        self.filter_counts.append(
            FilterCount(
                stage="acris_parties",
                rule_id="snapshot_dedup_party",
                rows_in=rows_in,
                rows_out=deduped.height,
            )
        )

        role = (
            pl.when(pl.col("party_type").cast(pl.Utf8) == "1")
            .then(pl.lit(PartyRole.GRANTOR.value))
            .when(pl.col("party_type").cast(pl.Utf8) == "2")
            .then(pl.lit(PartyRole.GRANTEE.value))
            .otherwise(None)
        )
        address_parts = []
        for col in ("address_1", "city", "state", "zip"):
            if col in deduped.columns:
                address_parts.append(pl.col(col).cast(pl.Utf8).fill_null("").str.strip_chars())
        if address_parts:
            address = (
                pl.concat_str(address_parts, separator=", ")
                .str.replace_all(r"(, )+", ", ")
                .str.strip_chars(", ")
            )
            address = pl.when(address == "").then(None).otherwise(address)
        else:
            address = pl.lit(None).cast(pl.Utf8)

        mapped = deduped.with_columns(
            pl.lit(self.metro_id).alias("metro_id"),
            pl.col("document_id").cast(pl.Utf8).alias("doc_id"),
            role.alias("role"),
            pl.col("name").cast(pl.Utf8).alias("name_raw"),
            address.alias("address_raw"),
        )
        mapped_in = mapped.height
        kept = mapped.filter(pl.col("role").is_not_null())
        self.filter_counts.append(
            FilterCount(
                stage="acris_parties",
                rule_id="party_type_grantor_grantee",
                rows_in=mapped_in,
                rows_out=kept.height,
            )
        )
        return kept.select("metro_id", "doc_id", "role", "name_raw", "address_raw")


def transfers_from_frame(df: pl.DataFrame) -> list[Transfer]:
    rows: list[Transfer] = []
    for row in df.iter_rows(named=True):
        payload = {**row}
        payload.pop("percent_trans", None)
        rows.append(Transfer.model_validate(payload))
    return rows


def parties_from_frame(df: pl.DataFrame) -> list[TransferParty]:
    return [TransferParty.model_validate(row) for row in df.iter_rows(named=True)]


def coverage_year(recorded: date | None) -> int | None:
    if recorded is None:
        return None
    return recorded.year
