"""NYC HPD registrations + contacts.

Field names were verified against tesw-yqqr and feu5-w2e2 on 2026-09-17.
See docs/data_sources.md and ADR 0007.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.bbl import format_bbl_parts
from opaque_housing.normalize.addresses import address_key, is_care_of, normalize_address
from opaque_housing.normalize.batch import attach_normalized_name
from opaque_housing.normalize.names import normalize_name, owner_key
from opaque_housing.quality.filters import FilterCount

SOURCE_DATASET = "nyc_hpd"
SOURCE_VERSION = "open-data-2026-09-17"

REG_REQUIRED = ("registrationid", "boroid", "block", "lot")
CONTACT_REQUIRED = ("registrationcontactid", "registrationid", "type")

# ADR 0007. Agent / SiteManager / Lessee are excluded.
O1_CONTACT_TYPES = frozenset(
    {"HeadOfficer", "IndividualOwner", "JointOwner", "Officer", "Shareholder"}
)


def _read_table(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    if suffix in {".csv", ".tsv"}:
        return pl.read_csv(path, infer_schema_length=0)
    raise ValueError(f"unsupported HPD extract suffix: {suffix}")


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.rename({name: name.lower() for name in df.columns})


def _require(df: pl.DataFrame, required: tuple[str, ...], label: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{label} extract missing required columns: {missing}")


def _fill(df: pl.DataFrame, name: str) -> pl.Expr:
    if name in df.columns:
        return pl.col(name).cast(pl.Utf8).fill_null("")
    return pl.lit("")


class NycHpdAdapter:
    metro_id = "nyc"

    def __init__(self, source_version: str = SOURCE_VERSION) -> None:
        self.source_version = source_version
        self.filter_counts: list[FilterCount] = []

    def load_registrations(self, path: Path) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(path))
        _require(raw, REG_REQUIRED, "hpd registrations")
        rows_in = raw.height
        parcel_ids = [
            format_bbl_parts(rec["boroid"], rec["block"], rec["lot"])
            for rec in raw.select(["boroid", "block", "lot"]).iter_rows(named=True)
        ]
        regs = raw.with_columns(
            pl.Series("parcel_id", parcel_ids),
            _fill(raw, "registrationid").alias("registrationid"),
            _fill(raw, "lastregistrationdate").alias("lastregistrationdate"),
            _fill(raw, "registrationenddate").alias("registrationenddate"),
        )
        valid = regs.filter(pl.col("parcel_id") != "")
        self.filter_counts.append(
            FilterCount("hpd_registrations", "valid_bbl", rows_in, valid.height)
        )
        return valid.select(
            [
                "registrationid",
                "parcel_id",
                "lastregistrationdate",
                "registrationenddate",
            ]
        )

    def latest_registration_per_parcel(self, registrations: pl.DataFrame) -> pl.DataFrame:
        rows_in = registrations.height
        if registrations.is_empty():
            self.filter_counts.append(
                FilterCount("hpd_registrations", "latest_per_bbl", rows_in, 0)
            )
            return registrations
        latest = (
            registrations.sort(["lastregistrationdate", "registrationid"])
            .group_by("parcel_id", maintain_order=True)
            .last()
        )
        self.filter_counts.append(
            FilterCount("hpd_registrations", "latest_per_bbl", rows_in, latest.height)
        )
        return latest

    def load_contacts(self, path: Path) -> pl.DataFrame:
        raw = _normalize_columns(_read_table(path))
        _require(raw, CONTACT_REQUIRED, "hpd contacts")
        rows_in = raw.height
        house = _fill(raw, "businesshousenumber")
        street = _fill(raw, "businessstreetname")
        apt = _fill(raw, "businessapartment")
        city = _fill(raw, "businesscity")
        state = _fill(raw, "businessstate")
        zipc = _fill(raw, "businesszip")
        first = _fill(raw, "firstname")
        last = _fill(raw, "lastname")
        corp = _fill(raw, "corporationname")
        work = raw.with_columns(
            _fill(raw, "registrationcontactid").alias("registrationcontactid"),
            _fill(raw, "registrationid").alias("registrationid"),
            _fill(raw, "type").alias("type"),
            _fill(raw, "contactdescription").alias("contactdescription"),
            _fill(raw, "title").alias("title"),
            first.alias("firstname"),
            last.alias("lastname"),
            corp.alias("corporationname"),
            house.alias("businesshousenumber"),
            street.alias("businessstreetname"),
            apt.alias("businessapartment"),
            city.alias("businesscity"),
            state.alias("businessstate"),
            zipc.alias("businesszip"),
        )
        address_rows = [
            normalize_address(
                rec["businesshousenumber"],
                rec["businessstreetname"],
                rec["businessapartment"],
                rec["businesscity"],
                rec["businessstate"],
                rec["businesszip"],
            )
            for rec in work.select(
                [
                    "businesshousenumber",
                    "businessstreetname",
                    "businessapartment",
                    "businesscity",
                    "businessstate",
                    "businesszip",
                ]
            ).iter_rows(named=True)
        ]
        care_of = [
            is_care_of(
                rec["businesshousenumber"],
                rec["businessstreetname"],
                rec["corporationname"],
            )
            for rec in work.select(
                ["businesshousenumber", "businessstreetname", "corporationname"]
            ).iter_rows(named=True)
        ]
        person_names = [
            normalize_name(f"{rec['firstname']} {rec['lastname']}".strip())
            for rec in work.select(["firstname", "lastname"]).iter_rows(named=True)
        ]
        contacts = work.with_columns(
            pl.Series("address_normalized", address_rows),
            pl.Series("is_care_of", care_of),
            pl.Series("person_name_normalized", person_names),
        ).with_columns(
            pl.col("address_normalized").map_elements(address_key, return_dtype=pl.Utf8).alias(
                "address_key"
            ),
            pl.col("person_name_normalized")
            .map_elements(lambda name: owner_key(name) if name else "", return_dtype=pl.Utf8)
            .alias("person_key"),
            (
                pl.col("type").is_in(list(O1_CONTACT_TYPES))
                & (pl.col("firstname") != "")
                & (pl.col("lastname") != "")
            ).alias("is_o1_person"),
        )
        contacts = attach_normalized_name(
            contacts,
            "corporationname",
            name_col="corporation_name_normalized",
            key_col="corporation_owner_key",
        )
        self.filter_counts.append(
            FilterCount("hpd_contacts", "loaded", rows_in, contacts.height)
        )
        return contacts

    def contacts_on_latest(
        self, contacts: pl.DataFrame, latest: pl.DataFrame
    ) -> pl.DataFrame:
        rows_in = contacts.height
        if contacts.is_empty() or latest.is_empty():
            self.filter_counts.append(
                FilterCount("hpd_contacts", "latest_registration", rows_in, 0)
            )
            return contacts.head(0)
        joined = contacts.join(
            latest.select(["registrationid", "parcel_id", "registrationenddate"]),
            on="registrationid",
            how="inner",
        )
        self.filter_counts.append(
            FilterCount("hpd_contacts", "latest_registration", rows_in, joined.height)
        )
        return joined
