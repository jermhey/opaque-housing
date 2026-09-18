"""Verified Miami-Dade GIS / Florida DOR identifiers. Inspected 2026-09-18."""

from __future__ import annotations

from dataclasses import dataclass

GIS_QUERY = (
    "https://gisweb.miamidade.gov/arcgis/rest/services/MD_LandInformation/MapServer/24/query"
)
GIS_OUT_FIELDS = (
    "FOLIO,TRUE_OWNER1,DOR_CODE_CUR,DOR_DESC,UNIT_COUNT,CONDO_FLAG,"
    "PARENT_FOLIO,TRUE_SITE_CITY,TRUE_SITE_ZIP_CODE,TRUE_MAILING_ADDR1,"
    "ASSESSMENT_YEAR_CUR,CANCEL_FLAG"
)
DADE_SNAPSHOT_DATE = "2026-01-01"
DADE_COUNTY_NO = "23"
GIS_FILENAME = "pagis_property.parquet"
SDF_FILENAME = "florida_sdf.csv"

# 2024/2025 DOR SDF user's guide, Section 2. Production files have no header.
SDF_FIELDS: tuple[str, ...] = (
    "CO_NO",
    "PARCEL_ID",
    "ASMNT_YR",
    "ATV_STRT",
    "GRP_NO",
    "DOR_UC",
    "NBRHD_CD",
    "MKT_AR",
    "CENSUS_BK",
    "SALE_ID_CD",
    "SAL_CHNG_CD",
    "VI_CD",
    "OR_BOOK",
    "OR_PAGE",
    "CLERK_NO",
    "QUAL_CD",
    "SALE_YR",
    "SALE_MO",
    "SALE_PRC",
    "MULTI_PAR_SAL",
    "RS_ID",
    "MP_ID",
    "STATE_PARCEL_ID",
)


@dataclass(frozen=True)
class DadeSpec:
    name: str
    filename: str
    kind: str


GIS = DadeSpec(name="gis", filename=GIS_FILENAME, kind="arcgis")
SDF = DadeSpec(name="sdf", filename=SDF_FILENAME, kind="local")
DADE_SOURCES: dict[str, DadeSpec] = {GIS.name: GIS, SDF.name: SDF}


def resolve_dade_specs(dataset: str) -> list[DadeSpec]:
    if dataset == "all":
        return [GIS]
    spec = DADE_SOURCES.get(dataset)
    if spec is None:
        raise KeyError(dataset)
    return [spec]
