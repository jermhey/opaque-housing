from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.building_type import (
    COOP_CLASSES,
    building_type_expr,
    building_type_from_pluto,
    is_residential_pluto,
    residential_expr,
)
from opaque_housing.schema import BuildingType

DOF_CODES = Path("src/opaque_housing/adapters/nyc/lookups/dof_building_classification_codes.csv")


def _type(bldgclass: str, landuse: int | None, unitsres: int) -> BuildingType:
    return building_type_from_pluto(
        bldgclass=bldgclass,
        landuse=landuse,
        unitsres=unitsres,
    )


def test_coop_identified_by_official_class_not_name() -> None:
    assert _type("C6", 2, 24) == BuildingType.COOP_BUILDING
    assert _type("D4", 3, 100) == BuildingType.COOP_BUILDING
    # A corporate-looking name is irrelevant; class D1 is not a co-op.
    assert _type("D1", 3, 48) == BuildingType.LARGE_MF


def test_condo_billing_and_residential_classes() -> None:
    assert _type("R0", None, 40) == BuildingType.CONDO_UNIT
    assert _type("R4", 3, 80) == BuildingType.CONDO_UNIT
    assert _type("RD", 3, 20) == BuildingType.CONDO_UNIT


def test_sfr_small_large_mixed_other() -> None:
    assert _type("A1", 1, 1) == BuildingType.SFR_1_4
    assert _type("C0", 2, 3) == BuildingType.SFR_1_4
    assert _type("C3", 2, 4) == BuildingType.SFR_1_4
    assert _type("C2", 2, 6) == BuildingType.SMALL_MF
    assert _type("S2", 4, 2) == BuildingType.MIXED_USE_RES
    assert _type("V0", 11, 0) == BuildingType.OTHER_RES


def test_residential_filter_keeps_housing_drops_vacant_and_city() -> None:
    assert is_residential_pluto(bldgclass="A1", landuse=1, unitsres=1)
    assert is_residential_pluto(bldgclass="A8", landuse=None, unitsres=0)
    assert is_residential_pluto(bldgclass="R0", landuse=None, unitsres=0)
    assert is_residential_pluto(bldgclass="S2", landuse=4, unitsres=2)
    assert not is_residential_pluto(bldgclass="V0", landuse=11, unitsres=0)
    assert not is_residential_pluto(bldgclass="Y5", landuse=8, unitsres=0)
    assert not is_residential_pluto(bldgclass="K1", landuse=5, unitsres=0)


def test_every_official_coop_code_is_in_dof_table() -> None:
    table = pl.read_csv(DOF_CODES)
    official = set(table["code"].to_list())
    assert COOP_CLASSES <= official


def test_polars_exprs_match_python_mappers() -> None:
    rows = [
        {"bldgclass": "A1", "landuse": "1", "unitsres": "1"},
        {"bldgclass": "C6", "landuse": "2", "unitsres": "24"},
        {"bldgclass": "R4", "landuse": "3", "unitsres": "80"},
        {"bldgclass": "C2", "landuse": "2", "unitsres": "6"},
        {"bldgclass": "D1", "landuse": "3", "unitsres": "48"},
        {"bldgclass": "S2", "landuse": "4", "unitsres": "2"},
        {"bldgclass": "V0", "landuse": "11", "unitsres": "0"},
        {"bldgclass": "Y5", "landuse": "8", "unitsres": "0"},
        {"bldgclass": "A8", "landuse": "", "unitsres": "0"},
    ]
    frame = pl.DataFrame(rows).with_columns(
        residential_expr().alias("keep"),
        building_type_expr().alias("type"),
    )
    for row, rec in zip(rows, frame.iter_rows(named=True), strict=True):
        assert rec["keep"] == is_residential_pluto(
            bldgclass=row["bldgclass"],
            landuse=row["landuse"] or None,
            unitsres=row["unitsres"],
        )
        if rec["keep"]:
            assert (
                rec["type"]
                == building_type_from_pluto(
                    bldgclass=row["bldgclass"],
                    landuse=row["landuse"] or None,
                    unitsres=row["unitsres"],
                ).value
            )
