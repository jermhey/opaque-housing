"""Verified Cook County Assessor SODA identifiers. Inspected 2026-09-18."""

from __future__ import annotations

from opaque_housing.adapters.nyc.sources import SourceSpec

SOCRATA_COOK = "https://datacatalog.cookcountyil.gov"
COOK_SNAPSHOT_DATE = "2026-01-01"
COOK_TAX_YEAR = "2026"

UNIVERSE_COLUMNS = (
    "pin,class,triad_name,township_name,nbhd_code,zip_code,"
    "cook_municipality_name,census_tract_geoid,year,row_id"
)
ADDRESS_COLUMNS = "pin,year,owner_address_name,mail_address_name,owner_address_full,row_id"
CHAR_COLUMNS = "pin,year,class,char_apts,row_id"
CONDO_COLUMNS = "pin,year,is_parking_space,is_common_area,row_id"
SALES_COLUMNS = (
    "pin,year,doc_no,sale_date,sale_price,deed_type,mydec_deed_type,"
    "buyer_name,seller_name,is_multisale,sale_filter_deed_type,"
    "sale_filter_less_than_10k,row_id"
)

UNIVERSE = SourceSpec(
    dataset_id="pabr-t5kh",
    name="universe",
    select=UNIVERSE_COLUMNS,
    limit=50_000,
    filename="pabr-t5kh.parquet",
    paged=True,
    key="pin",
    host=SOCRATA_COOK,
)
ADDRESSES = SourceSpec(
    dataset_id="3723-97qp",
    name="addresses",
    select=ADDRESS_COLUMNS,
    limit=50_000,
    filename="3723-97qp.parquet",
    where=f"year={COOK_TAX_YEAR}",
    paged=True,
    key="row_id",
    host=SOCRATA_COOK,
)
CHARACTERISTICS = SourceSpec(
    dataset_id="x54s-btds",
    name="characteristics",
    select=CHAR_COLUMNS,
    limit=50_000,
    filename="x54s-btds.parquet",
    where=f"year={COOK_TAX_YEAR}",
    paged=True,
    key="row_id",
    host=SOCRATA_COOK,
)
CONDO = SourceSpec(
    dataset_id="3r7i-mrz4",
    name="condo",
    select=CONDO_COLUMNS,
    limit=50_000,
    filename="3r7i-mrz4.parquet",
    where=f"year={COOK_TAX_YEAR}",
    paged=True,
    key="row_id",
    host=SOCRATA_COOK,
)
SALES = SourceSpec(
    dataset_id="wvhk-k5uv",
    name="sales",
    select=SALES_COLUMNS,
    limit=50_000,
    filename="wvhk-k5uv.parquet",
    paged=True,
    key="row_id",
    host=SOCRATA_COOK,
)

COOK_SOURCES: dict[str, SourceSpec] = {
    UNIVERSE.name: UNIVERSE,
    ADDRESSES.name: ADDRESSES,
    CHARACTERISTICS.name: CHARACTERISTICS,
    CONDO.name: CONDO,
    SALES.name: SALES,
}

COOK_STOCK_DATASETS = ("universe", "addresses", "characteristics", "condo")


def resolve_cook_specs(dataset: str) -> list[SourceSpec]:
    if dataset == "all":
        return [COOK_SOURCES[name] for name in COOK_STOCK_DATASETS]
    spec = COOK_SOURCES.get(dataset)
    if spec is None:
        raise KeyError(dataset)
    return [spec]
