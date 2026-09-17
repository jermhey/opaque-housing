"""Verified NYC Open Data / OPEN NY identifiers. Do not invent IDs here."""

from __future__ import annotations

from dataclasses import dataclass

# Dataset IDs were read from the live catalogs on 2026-09-16. See docs/data_sources.md.
SOCRATA_NYC = "https://data.cityofnewyork.us"


@dataclass(frozen=True)
class SourceSpec:
    dataset_id: str
    name: str
    # $select uses only fields recorded in docs/data_sources.md.
    select: str
    limit: int
    filename: str

    @property
    def csv_url(self) -> str:
        return (
            f"{SOCRATA_NYC}/resource/{self.dataset_id}.csv"
            f"?$select={self.select}&$limit={self.limit}"
        )


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

# DCP PLUTO 26v2 readme is dated August 2026.
PLUTO_SNAPSHOT_DATE = "2026-08-01"
