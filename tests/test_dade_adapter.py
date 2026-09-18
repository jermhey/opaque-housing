from datetime import date
from pathlib import Path

from opaque_housing.adapters.base import MetroAdapter
from opaque_housing.adapters.dade.building_type import building_type_and_units, is_residential
from opaque_housing.adapters.dade.parcels import DadeParcelAdapter, parcels_from_frame
from opaque_housing.adapters.dade.sdf import DadeSdfAdapter
from opaque_housing.adapters.dade.sources import DADE_COUNTY_NO, SDF_FIELDS, resolve_dade_specs
from opaque_housing.schema import BuildingType, DocTypeCanonical

GIS = Path("tests/fixtures/dade/gis_sample.csv")
SDF = Path("tests/fixtures/dade/sdf_sample.csv")


def test_adapter_satisfies_protocol() -> None:
    adapter = DadeParcelAdapter(snapshot_date=date(2026, 1, 1))
    assert isinstance(adapter, MetroAdapter)


def test_building_type_dor_desc() -> None:
    assert building_type_and_units("RESIDENTIAL - SINGLE FAMILY : 1 UNIT", 1) == (
        BuildingType.SFR_1_4,
        1,
    )
    assert building_type_and_units("MULTIFAMILY 2-9 UNITS : 2 LIVING UNITS", 2) == (
        BuildingType.SFR_1_4,
        2,
    )
    assert building_type_and_units("MULTIFAMILY 2-9 UNITS : MULTIFAMILY 3 OR MORE UNITS", 5) == (
        BuildingType.SMALL_MF,
        5,
    )
    assert building_type_and_units(
        "MULTIFAMILY 10 UNITS PLUS : MULTIFAMILY 3 OR MORE UNITS", 24
    ) == (
        BuildingType.LARGE_MF,
        24,
    )
    assert building_type_and_units("RESIDENTIAL - TOTAL VALUE : CONDOMINIUM - RESIDENTIAL", 1) == (
        BuildingType.CONDO_UNIT,
        1,
    )
    assert building_type_and_units("COOPERATIVE - RESIDENTIAL : COOPERATIVE - RESIDENTIAL", 1) == (
        BuildingType.COOP_BUILDING,
        1,
    )
    assert is_residential("VACANT RESIDENTIAL : VACANT LAND") is False
    assert is_residential("RESIDENTIAL - SINGLE FAMILY : 1 UNIT", "Y") is False
    assert is_residential("RESIDENTIAL - SINGLE FAMILY : 1 UNIT") is True


def test_gis_fixture_maps_to_canonical_parcels() -> None:
    adapter = DadeParcelAdapter(snapshot_date=date(2026, 1, 1))
    frame = adapter.load_parcels_snapshot(GIS)
    rows = parcels_from_frame(frame)
    counts = adapter.filter_counts[-1]
    assert counts.rule_id == "dade_residential_only"
    assert counts.rows_in == 9
    assert counts.rows_out == 8
    by_id = {row.parcel_id: row for row in rows}
    assert by_id["0101000000001"].building_type == BuildingType.SFR_1_4
    assert by_id["0101000000001"].geo_borough == "Miami"
    assert by_id["0101000000001"].geo_neighborhood == "33131"
    assert by_id["0101000000002"].building_type == BuildingType.SFR_1_4
    assert by_id["0101000000002"].res_units == 2
    assert by_id["0101000000002"].geo_borough == "Hialeah"
    assert by_id["0101000000003"].building_type == BuildingType.LARGE_MF
    assert by_id["0101000000003"].res_units == 24
    assert by_id["0101000000004"].building_type == BuildingType.CONDO_UNIT
    assert by_id["0101000000005"].building_type == BuildingType.COOP_BUILDING
    assert by_id["0101000000007"].owner_name_raw == "CITY OF MIAMI"
    assert by_id["0101000000008"].owner_name_raw in {None, ""}
    assert by_id["0101000000009"].building_type == BuildingType.SMALL_MF
    assert by_id["0101000000009"].res_units == 5
    assert "0101000000006" not in by_id
    assert all(row.metro_id == "dade" for row in rows)


def test_sdf_fixture_filters_county_and_qual() -> None:
    adapter = DadeSdfAdapter()
    frame = adapter.load_transfers(SDF)
    assert frame.height == 2
    by_id = {row["doc_id"]: row for row in frame.iter_rows(named=True)}
    assert by_id["CK1"]["doc_type_canonical"] == DocTypeCanonical.SALE_DEED.value
    assert by_id["CK1"]["consideration"] == 250000
    assert by_id["CK1"]["grantee_name_raw"] is None
    assert by_id["CK2"]["doc_type_canonical"] == DocTypeCanonical.OTHER.value
    assert "CK3" not in by_id


def test_headerless_sdf(tmp_path: Path) -> None:
    values = {name: "" for name in SDF_FIELDS}
    values.update(
        {
            "CO_NO": "23",
            "PARCEL_ID": "0101000000001",
            "ASMNT_YR": "2025",
            "QUAL_CD": "01",
            "SALE_YR": "2022",
            "SALE_MO": "06",
            "SALE_PRC": "250000",
            "CLERK_NO": "CK9",
        }
    )
    path = tmp_path / "sdf.csv"
    path.write_text(",".join(values[name] for name in SDF_FIELDS) + "\n")
    adapter = DadeSdfAdapter()
    frame = adapter.load_transfers(path)
    assert frame.height == 1
    row = frame.row(0, named=True)
    assert row["doc_id"] == "CK9"
    assert row["doc_type_canonical"] == DocTypeCanonical.SALE_DEED.value
    assert row["consideration"] == 250000
    assert DADE_COUNTY_NO == "23"


def test_resolve_dade_specs() -> None:
    names = [spec.name for spec in resolve_dade_specs("all")]
    assert names == ["gis"]
    sdf = resolve_dade_specs("sdf")
    assert sdf[0].kind == "local"
