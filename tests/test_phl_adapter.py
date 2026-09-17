from datetime import date
from pathlib import Path

from opaque_housing.adapters.base import MetroAdapter
from opaque_housing.adapters.phl.building_type import building_type_and_units, is_residential
from opaque_housing.adapters.phl.opa import PhlOpaAdapter, format_parcel_number, parcels_from_frame
from opaque_housing.adapters.phl.rtt import SALE_TYPES, PhlRttAdapter
from opaque_housing.schema import BuildingType, DocTypeCanonical

FIXTURE = Path("tests/fixtures/phl/opa_sample.csv")
RTT = Path("tests/fixtures/phl/rtt_sample.csv")


def test_adapter_satisfies_protocol() -> None:
    adapter = PhlOpaAdapter(snapshot_date=date(2026, 4, 29))
    assert isinstance(adapter, MetroAdapter)


def test_format_parcel_number() -> None:
    assert format_parcel_number("433365300") == "433365300"
    assert format_parcel_number(123456789) == "123456789"


def test_building_type_lower_bounds() -> None:
    assert building_type_and_units("1", "ROW 2 STY MASONRY") == (BuildingType.SFR_1_4, 1)
    assert building_type_and_units("1", "RES CONDO 5+ STY MASONRY") == (BuildingType.CONDO_UNIT, 1)
    assert building_type_and_units("2", "APT 2-4 UNITS 2 STY MASON") == (BuildingType.SFR_1_4, 2)
    assert building_type_and_units("2", "APTS 5-50 UNITS MASONRY") == (BuildingType.SMALL_MF, 5)
    assert building_type_and_units("2", "APTS 100+ UNITS MASONRY") == (BuildingType.LARGE_MF, 100)
    assert is_residential("6", "VACANT LAND RESIDE < ACRE") is False
    assert is_residential("1", "CONDO PARKING SPACE") is False
    assert is_residential("1", "ROW 2 STY MASONRY") is True


def test_opa_fixture_maps_to_canonical_parcels() -> None:
    adapter = PhlOpaAdapter(snapshot_date=date(2026, 4, 29))
    frame = adapter.load_parcels_snapshot(FIXTURE)
    rows = parcels_from_frame(frame)
    counts = adapter.filter_counts[-1]
    assert counts.rule_id == "opa_residential_only"
    assert counts.rows_in == 10
    assert counts.rows_out == 8
    by_id = {row.parcel_id: row for row in rows}
    assert by_id["123456789"].building_type == BuildingType.SFR_1_4
    assert by_id["123456789"].res_units == 1
    assert by_id["123456789"].geo_borough == "Philadelphia"
    assert by_id["123456789"].geo_neighborhood == "19140"
    assert by_id["123456789"].geo_tract is None
    assert by_id["222222222"].res_units == 2
    assert by_id["444444444"].building_type == BuildingType.CONDO_UNIT
    assert by_id["555555555"].building_type == BuildingType.SMALL_MF
    assert by_id["101010101"].res_units == 100
    assert "888888888" not in by_id
    assert "999999999" not in by_id
    assert all(row.metro_id == "phl" for row in rows)


def test_rtt_fixture_marks_deeds() -> None:
    adapter = PhlRttAdapter()
    frame = adapter.load_transfers(RTT)
    assert frame.height == 3
    deeds = frame.filter(pl_doc_is_sale(frame))
    assert deeds.height == 2
    assert SALE_TYPES == frozenset({"DEED"})


def pl_doc_is_sale(frame):
    return frame["doc_type_canonical"] == DocTypeCanonical.SALE_DEED.value
