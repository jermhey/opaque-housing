"""Verified Philadelphia / Pennsylvania identifiers. Do not invent IDs here."""

from __future__ import annotations

from dataclasses import dataclass

# Table names and columns were read from live Carto / Socrata on 2026-09-17.
CARTO_PHL = "https://phl.carto.com"
SOCRATA_PA = "https://data.pa.gov"

OPA_COLUMNS = (
    "parcel_number,owner_1,owner_2,mailing_street,mailing_address_1,"
    "mailing_city_state,mailing_zip,category_code,category_code_description,"
    "building_code,building_code_description,census_tract,zip_code,unit,"
    "assessment_date,geographic_ward"
)

RTT_COLUMNS = (
    "document_id,document_type,recording_date,display_date,grantors,grantees,"
    "total_consideration,opa_account_num,zip_code,ward,property_count,record_id"
)


@dataclass(frozen=True)
class CartoSpec:
    table: str
    name: str
    select: str
    filename: str
    where: str | None = None
    host: str = CARTO_PHL

    @property
    def query(self) -> str:
        sql = f"SELECT {self.select} FROM {self.table}"
        if self.where:
            sql += f" WHERE {self.where}"
        return sql


OPA = CartoSpec(
    table="opa_properties_public",
    name="opa",
    select=OPA_COLUMNS,
    filename="opa_properties_public.csv",
)

RTT = CartoSpec(
    table="rtt_summary",
    name="rtt",
    select=RTT_COLUMNS,
    filename="rtt_summary.csv",
    where="document_type='DEED'",
)

PHL_SOURCES: dict[str, CartoSpec] = {OPA.name: OPA, RTT.name: RTT}

# Current PA DOS list. No officer names. Not used for O-tiers (ADR 0010).
PA_DOS_DATASET_ID = "3urc-uaba"
OPA_SNAPSHOT_DATE = "2026-04-29"


def resolve_phl_specs(dataset: str) -> list[CartoSpec]:
    if dataset == "all":
        return [OPA]
    if dataset == "rtt":
        return [RTT]
    spec = PHL_SOURCES.get(dataset)
    if spec is None:
        raise KeyError(dataset)
    return [spec]
