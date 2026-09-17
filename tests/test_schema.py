from datetime import date

from opaque_housing.schema import (
    ENTITY_OWNED_CLASSES,
    BuildingType,
    OwnerClass,
    ParcelSnapshot,
)


def test_parcel_snapshot_round_trip() -> None:
    row = ParcelSnapshot(
        metro_id="nyc",
        parcel_id="3001230045",
        snapshot_date=date(2026, 5, 28),
        geo_tract="36047012300",
        geo_neighborhood="BK0101",
        building_type=BuildingType.SFR_1_4,
        res_units=2,
        owner_name_raw="123 MAIN ST LLC",
        owner_mailing_address_raw="1 BROADWAY NEW YORK NY 10004",
        source_dataset="pluto",
        source_version="26v1",
    )
    assert row.model_dump()["building_type"] == "sfr_1_4"


def test_headline_entity_grouping_excludes_trusts() -> None:
    assert OwnerClass.TRUST not in ENTITY_OWNED_CLASSES
    assert OwnerClass.LLC in ENTITY_OWNED_CLASSES
    assert OwnerClass.CORP in ENTITY_OWNED_CLASSES
    assert OwnerClass.PARTNERSHIP in ENTITY_OWNED_CLASSES
