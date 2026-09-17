from datetime import date
from pathlib import Path

from opaque_housing.adapters.base import MetroAdapter
from opaque_housing.adapters.nyc.pluto import (
    NycPlutoAdapter,
    format_bbl,
    parcels_from_frame,
)
from opaque_housing.schema import BuildingType

FIXTURE = Path("tests/fixtures/nyc/pluto_sample.csv")
EQUIV = Path("tests/fixtures/nyc/tract_nta_equiv_sample.csv")
PARQUET = Path("tests/fixtures/nyc/pluto_sample.parquet")


def test_adapter_satisfies_protocol() -> None:
    adapter = NycPlutoAdapter(snapshot_date=date(2026, 8, 1))
    assert isinstance(adapter, MetroAdapter)


def test_format_bbl_strips_socrata_decimal() -> None:
    assert format_bbl("4087860042.00000000") == "4087860042"
    assert format_bbl(1000010001) == "1000010001"
    assert format_bbl(None) == ""


def test_pluto_fixture_maps_to_canonical_parcels() -> None:
    adapter = NycPlutoAdapter(
        snapshot_date=date(2026, 8, 1),
        tract_equiv_path=EQUIV,
    )
    raw_n = FIXTURE.read_text().count("\n") - 1
    frame = adapter.load_parcels_snapshot(FIXTURE)
    rows = parcels_from_frame(frame)
    counts = adapter.filter_counts[-1]

    assert raw_n == 9
    assert counts.rule_id == "pluto_residential_only"
    assert counts.rows_in == 9
    assert counts.rows_out == 7
    assert len(rows) == 7
    assert {row.metro_id for row in rows} == {"nyc"}
    assert all(row.source_dataset == "nyc_pluto" for row in rows)
    assert all(row.source_version == "26v2" for row in rows)
    assert all(row.owner_mailing_address_raw is None for row in rows)
    assert all(row.snapshot_date == date(2026, 8, 1) for row in rows)

    by_id = {row.parcel_id: row for row in rows}
    assert by_id["1000010001"].building_type == BuildingType.SFR_1_4
    assert by_id["1000010001"].geo_tract == "36061002100"
    assert by_id["1000010001"].geo_neighborhood == "MN0101"
    assert by_id["1000120020"].building_type == BuildingType.COOP_BUILDING
    assert by_id["1000207501"].building_type == BuildingType.CONDO_UNIT
    assert by_id["3001000010"].building_type == BuildingType.SMALL_MF
    assert by_id["3002000005"].building_type == BuildingType.LARGE_MF
    assert by_id["4000500001"].building_type == BuildingType.MIXED_USE_RES
    assert "5000100001" not in by_id  # city / non-residential
    assert "2000800003" not in by_id  # vacant


def test_pluto_parquet_fixture_round_trip() -> None:
    adapter = NycPlutoAdapter(snapshot_date=date(2026, 8, 1))
    rows = parcels_from_frame(adapter.load_parcels_snapshot(PARQUET))
    assert len(rows) == 7
