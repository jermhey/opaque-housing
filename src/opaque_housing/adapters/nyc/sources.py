"""Verified NYC Open Data / OPEN NY identifiers. Do not invent IDs here."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

# Dataset IDs were read from the live catalogs on 2026-09-16. See docs/data_sources.md.
SOCRATA_NYC = "https://data.cityofnewyork.us"

# Electronic ACRIS ids and usable document_amt begin in 2003 (ADR 0006).
ACRIS_ID_WINDOW = "document_id>='2003010100000000' and document_id<'2027010100000000'"
ACRIS_SALE_AND_NEAR_TYPES = (
    "doc_type in('DEED','DEED, RC','DEEDP','DEEDO','REIT','ASTU',"
    "'CORRD','CONDEED','DEED COR','TODD','IDED','DEED, LE','DEED, TS')"
    " and date_extract_y(recorded_datetime)>=2003"
    " and date_extract_y(recorded_datetime)<=2026"
)


@dataclass(frozen=True)
class SourceSpec:
    dataset_id: str
    name: str
    # $select uses only fields recorded in docs/data_sources.md.
    select: str
    limit: int
    filename: str
    where: str | None = None
    paged: bool = False
    key: str = "document_id"

    @property
    def csv_url(self) -> str:
        url = (
            f"{SOCRATA_NYC}/resource/{self.dataset_id}.csv"
            f"?$select={self.select}&$limit={self.limit}"
        )
        if self.where:
            url += f"&$where={quote(self.where, safe=",()'>=<* ")}"
        return url


PLUTO = SourceSpec(
    dataset_id="64uk-42ks",
    name="pluto",
    select="bbl,bldgclass,unitsres,ownername,version,bct2020,borocode,landuse,condono",
    limit=1_000_000,
    filename="64uk-42ks.csv",
)

TRACT_NTA = SourceSpec(
    dataset_id="hm78-6dwm",
    name="tract_nta",
    select="geoid,countyfips,borocode,boroname,boroct2020,ct2020,ntacode,ntaname",
    limit=5_000,
    filename="hm78-6dwm.csv",
)

NYC_SOURCES: dict[str, SourceSpec] = {
    PLUTO.name: PLUTO,
    TRACT_NTA.name: TRACT_NTA,
}

ACRIS_MASTER = SourceSpec(
    dataset_id="bnx9-e6tj",
    name="acris_master",
    select=(
        "document_id,doc_type,document_date,document_amt,"
        "recorded_datetime,percent_trans,good_through_date"
    ),
    limit=50_000,
    filename="bnx9-e6tj.parquet",
    where=ACRIS_SALE_AND_NEAR_TYPES,
    paged=True,
)

ACRIS_LEGALS = SourceSpec(
    dataset_id="8h5j-fqxa",
    name="acris_legals",
    select="document_id,borough,block,lot,unit,partial_lot,good_through_date",
    limit=50_000,
    filename="8h5j-fqxa.parquet",
    where=ACRIS_ID_WINDOW,
    paged=True,
)

ACRIS_PARTIES = SourceSpec(
    dataset_id="636b-3b5g",
    name="acris_parties",
    select="document_id,party_type,name,address_1,city,state,zip,good_through_date",
    limit=50_000,
    filename="636b-3b5g.parquet",
    where=ACRIS_ID_WINDOW,
    paged=True,
)

ACRIS_SOURCES: dict[str, SourceSpec] = {
    ACRIS_MASTER.name: ACRIS_MASTER,
    ACRIS_LEGALS.name: ACRIS_LEGALS,
    ACRIS_PARTIES.name: ACRIS_PARTIES,
}


def resolve_ingest_specs(dataset: str) -> list[SourceSpec]:
    if dataset == "all":
        return list(NYC_SOURCES.values())
    if dataset == "acris":
        return list(ACRIS_SOURCES.values())
    spec = NYC_SOURCES.get(dataset) or ACRIS_SOURCES.get(dataset)
    if spec is None:
        raise KeyError(dataset)
    return [spec]


# DCP PLUTO 26v2 readme is dated August 2026.
PLUTO_SNAPSHOT_DATE = "2026-08-01"
