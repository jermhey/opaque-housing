from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.acris import NycAcrisAdapter
from opaque_housing.adapters.nyc.pad import load_pad_crosswalk
from opaque_housing.adapters.nyc.pluto import NycPlutoAdapter
from opaque_housing.classify.apply import classify_parcel_frame
from opaque_housing.metrics.flow import (
    attach_residential,
    classify_buyers,
    flow_headlines,
    history_only_sales,
    in_coverage_window,
    sensitivity_table,
    with_year_and_borough,
)
from opaque_housing.metrics.history import consistency_check, historical_stock_table, owner_as_of
from opaque_housing.metrics.sale_filter import (
    SaleFilterConfig,
    apply_sale_filter,
    attach_primary_parties,
)

MASTER = Path("tests/fixtures/nyc/acris_master.csv")
LEGALS = Path("tests/fixtures/nyc/acris_legals.csv")
PARTIES = Path("tests/fixtures/nyc/acris_parties.csv")
PAD = Path("tests/fixtures/nyc/pad_bbl_sample.csv")
PLUTO = Path("tests/fixtures/nyc/pluto_sample.csv")
EQUIV = Path("tests/fixtures/nyc/tract_nta_equiv_sample.csv")


def _parcels():
    adapter = NycPlutoAdapter(snapshot_date=date(2026, 8, 1), tract_equiv_path=EQUIV)
    return classify_parcel_frame(adapter.load_parcels_snapshot(PLUTO))


def _attached(config: SaleFilterConfig | None = None):
    acris = NycAcrisAdapter()
    transfers = attach_primary_parties(
        acris.load_transfers(MASTER, LEGALS),
        acris.load_transfer_parties(PARTIES),
    )
    filtered, _ = apply_sale_filter(transfers, config or SaleFilterConfig())
    buyers = classify_buyers(filtered)
    matched, counts = attach_residential(buyers, _parcels(), load_pad_crosswalk(PAD))
    return with_year_and_borough(matched), counts, transfers


def test_condo_unit_joins_via_pad_and_counts_as_one_unit() -> None:
    matched, counts, _ = _attached()
    condo = matched.filter(pl.col("doc_id") == "D2020CONDO")
    assert condo.height == 1
    assert condo["building_type"][0] == "condo_unit"
    assert condo["res_units"][0] == 1
    assert counts[-1].rows_out >= 1


def test_multi_parcel_deed_is_one_purchase() -> None:
    matched, _, _ = _attached()
    headlines = flow_headlines(matched)
    assert headlines["private_residential"]["sales"] >= 1
    multi = matched.filter(pl.col("doc_id") == "D2020MULTI")
    assert multi.height == 2
    entity_docs = set(matched.filter(pl.col("is_entity"))["doc_id"].to_list())
    assert "D2004SALE" in entity_docs
    assert "D2018FAM" not in entity_docs


def test_coverage_window_drops_outside_years() -> None:
    matched, _, _ = _attached()
    extra = matched.with_columns(pl.lit(1999).alias("year"))
    kept, count = in_coverage_window(extra)
    assert count.rows_out == 0
    assert kept.is_empty()


def test_history_keeps_zero_amount_and_reconstructs_chain() -> None:
    acris = NycAcrisAdapter()
    transfers = attach_primary_parties(
        acris.load_transfers(MASTER, LEGALS),
        acris.load_transfer_parties(PARTIES),
    )
    hist, _ = history_only_sales(transfers)
    buyers = classify_buyers(hist)
    matched, _ = attach_residential(buyers, _parcels(), load_pad_crosswalk(PAD))
    lot = matched.filter(pl.col("parcel_id") == "1000010001")
    as_2010 = owner_as_of(lot, date(2010, 12, 31))
    as_2016 = owner_as_of(lot, date(2016, 12, 31))
    as_2019 = owner_as_of(lot, date(2019, 12, 31))
    assert as_2010["buyer_class"][0] == "llc"
    assert as_2016["buyer_class"][0] == "individual"
    assert as_2019["buyer_class"][0] == "individual"
    table = historical_stock_table(matched, _parcels(), [date(2015, 12, 31)])
    assert table.height == 1
    assert table["parcels"][0] >= 1


def test_consistency_compares_reconstructed_to_pluto() -> None:
    acris = NycAcrisAdapter()
    transfers = attach_primary_parties(
        acris.load_transfers(MASTER, LEGALS),
        acris.load_transfer_parties(PARTIES),
    )
    hist, _ = history_only_sales(transfers)
    matched, _ = attach_residential(classify_buyers(hist), _parcels(), load_pad_crosswalk(PAD))
    report = consistency_check(matched, _parcels(), date(2026, 8, 1))
    assert report["n_compared"] >= 1
    assert 0 <= report["class_agree_rate"] <= 1


def test_sensitivity_table_has_named_configs() -> None:
    _, _, transfers = _attached()
    table = sensitivity_table(transfers, _parcels(), load_pad_crosswalk(PAD))
    names = set(table["config"].to_list())
    assert "default_10k" in names
    assert "zero_as_missing_10k" in names
    assert "exclude_astu" in names
    default = table.filter(pl.col("config") == "default_10k")
    zero = table.filter(pl.col("config") == "threshold_0")
    assert zero["sales"][0] >= default["sales"][0]
