from datetime import date
from pathlib import Path

from opaque_housing.adapters.base import MetroAdapter
from opaque_housing.adapters.cook.building_type import building_type_and_units, is_residential
from opaque_housing.adapters.cook.parcels import CookParcelAdapter, format_pin, parcels_from_frame
from opaque_housing.adapters.cook.sales import CookSalesAdapter
from opaque_housing.adapters.cook.sources import resolve_cook_specs
from opaque_housing.schema import BuildingType, DocTypeCanonical

UNIVERSE = Path("tests/fixtures/cook/universe.csv")
ADDRESSES = Path("tests/fixtures/cook/addresses.csv")
CHARS = Path("tests/fixtures/cook/characteristics.csv")
CONDO = Path("tests/fixtures/cook/condo.csv")
SALES = Path("tests/fixtures/cook/sales.csv")


def test_adapter_satisfies_protocol() -> None:
    adapter = CookParcelAdapter(snapshot_date=date(2026, 1, 1))
    assert isinstance(adapter, MetroAdapter)


def test_format_pin() -> None:
    assert format_pin("14021250150000") == "14021250150000"
    assert format_pin(14021250150000) == "14021250150000"


def test_building_type_class_211_split() -> None:
    assert building_type_and_units("203") == (BuildingType.SFR_1_4, 1)
    assert building_type_and_units("211", char_apts="Two") == (BuildingType.SFR_1_4, 2)
    assert building_type_and_units("211", char_apts="Six") == (BuildingType.SMALL_MF, 6)
    assert building_type_and_units("212", char_apts="Three") == (BuildingType.MIXED_USE_RES, 3)
    assert building_type_and_units("213") == (BuildingType.COOP_BUILDING, 1)
    assert building_type_and_units("299") == (BuildingType.CONDO_UNIT, 1)
    assert building_type_and_units("299", parking=True) is None
    assert building_type_and_units("313") == (BuildingType.SMALL_MF, 7)
    assert is_residential("100") is False
    assert is_residential("203") is True


def test_universe_fixture_maps_to_canonical_parcels() -> None:
    adapter = CookParcelAdapter(snapshot_date=date(2026, 1, 1))
    frame = adapter.load_parcels_snapshot(
        UNIVERSE,
        addresses_path=ADDRESSES,
        characteristics_path=CHARS,
        condo_path=CONDO,
    )
    rows = parcels_from_frame(frame)
    counts = adapter.filter_counts[-1]
    assert counts.rule_id == "cook_residential_only"
    assert counts.rows_in == 8
    assert counts.rows_out == 6
    by_id = {row.parcel_id: row for row in rows}
    assert by_id["14021250150000"].building_type == BuildingType.SFR_1_4
    assert by_id["14021250150000"].res_units == 1
    assert by_id["14021250150000"].owner_name_raw == "JANE SMITH"
    assert by_id["14021250150000"].geo_borough == "Lake View"
    assert by_id["14021250150000"].geo_neighborhood == "Lake View 22010"
    assert by_id["14021250150001"].building_type == BuildingType.SFR_1_4
    assert by_id["14021250150001"].res_units == 2
    assert by_id["14021250150002"].building_type == BuildingType.SMALL_MF
    assert by_id["14021250150002"].res_units == 6
    assert by_id["14021250150003"].building_type == BuildingType.CONDO_UNIT
    assert by_id["14021250150005"].building_type == BuildingType.SMALL_MF
    assert by_id["14021250150007"].building_type == BuildingType.COOP_BUILDING
    assert "14021250150004" not in by_id
    assert "14021250150006" not in by_id
    assert all(row.metro_id == "cook" for row in rows)


def test_sales_fixture_marks_deeds() -> None:
    adapter = CookSalesAdapter()
    frame = adapter.load_transfers(SALES)
    assert frame.height == 3
    by_id = {row["doc_id"]: row for row in frame.iter_rows(named=True)}
    assert by_id["D1"]["doc_type_canonical"] == DocTypeCanonical.SALE_DEED.value
    assert by_id["D1"]["consideration"] == 250000
    assert by_id["D1"]["grantee_name_raw"] == "BUYER LLC"
    assert "14021250150000" in by_id["D1"]["parcel_ids"]
    assert by_id["D2"]["doc_type_canonical"] == DocTypeCanonical.SALE_DEED.value
    assert by_id["D3"]["doc_type_canonical"] == DocTypeCanonical.OTHER.value


def test_resolve_cook_specs() -> None:
    names = [spec.name for spec in resolve_cook_specs("all")]
    assert names == ["universe", "addresses", "characteristics", "condo"]
    sales = resolve_cook_specs("sales")
    assert sales[0].dataset_id == "wvhk-k5uv"
