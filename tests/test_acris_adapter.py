from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.acris import (
    NycAcrisAdapter,
    parties_from_frame,
    transfers_from_frame,
)
from opaque_housing.adapters.nyc.bbl import format_bbl_parts
from opaque_housing.adapters.nyc.pad import crosswalk_from_frame, load_pad_crosswalk, map_to_billing
from opaque_housing.schema import DocTypeCanonical, PartyRole

MASTER = Path("tests/fixtures/nyc/acris_master.csv")
LEGALS = Path("tests/fixtures/nyc/acris_legals.csv")
PARTIES = Path("tests/fixtures/nyc/acris_parties.csv")
PAD = Path("tests/fixtures/nyc/pad_bbl_sample.csv")


def test_format_bbl_parts() -> None:
    assert format_bbl_parts("1", "1", "1") == "1000010001"
    assert format_bbl_parts(3, 100, 10) == "3001000010"
    assert format_bbl_parts("", "1", "1") == ""


def test_adapter_dedups_snapshots_and_maps_types() -> None:
    adapter = NycAcrisAdapter()
    transfers = adapter.load_transfers(MASTER, LEGALS)
    rows = {row.doc_id: row for row in transfers_from_frame(transfers)}
    assert "D2004SALE" in rows
    assert rows["D2004SALE"].doc_type_canonical is DocTypeCanonical.SALE_DEED
    assert rows["D2004SALE"].parcel_ids == ["1000010001"]
    assert rows["D2004SALE"].consideration == 500000
    assert rows["D2004SALE"].recorded_date == date(2004, 6, 15)
    assert rows["D2016CORR"].doc_type_canonical is DocTypeCanonical.NONSALE_DEED
    assert rows["D2022MTGE"].doc_type_canonical is DocTypeCanonical.OTHER
    assert sorted(rows["D2020MULTI"].parcel_ids) == ["3001000010", "3002000005"]
    master_count = next(
        item for item in adapter.filter_counts if item.rule_id == "snapshot_dedup_document_id"
    )
    assert master_count.rows_in == 12
    assert master_count.rows_out == 11


def test_parties_drop_type_3_and_dedup() -> None:
    adapter = NycAcrisAdapter()
    parties = adapter.load_transfer_parties(PARTIES)
    models = parties_from_frame(parties)
    sale = [row for row in models if row.doc_id == "D2004SALE"]
    assert {row.role for row in sale} == {PartyRole.GRANTOR, PartyRole.GRANTEE}
    assert len(sale) == 2
    none = [row for row in models if row.doc_id == "D2024NONE"]
    assert [row.role for row in none] == [PartyRole.GRANTOR]
    dropped = next(
        item for item in adapter.filter_counts if item.rule_id == "party_type_grantor_grantee"
    )
    assert dropped.rows_out < dropped.rows_in


def test_pad_maps_unit_lot_to_billing_lot() -> None:
    crosswalk = load_pad_crosswalk(PAD)
    mapped = map_to_billing(pl.Series(["1000201101", "1000010001"]), crosswalk)
    by_unit = {row["unit_parcel_id"]: row for row in mapped.iter_rows(named=True)}
    assert by_unit["1000201101"]["billing_parcel_id"] == "1000207501"
    assert by_unit["1000201101"]["is_condo_unit"] is True
    assert by_unit["1000010001"]["billing_parcel_id"] == "1000010001"
    assert by_unit["1000010001"]["is_condo_unit"] is False


def test_pad_requires_official_columns() -> None:
    try:
        crosswalk_from_frame(pl.DataFrame({"x": [1]}))
    except ValueError as exc:
        assert "boro" in str(exc)
    else:
        raise AssertionError("expected missing-column error")
