from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.pluto import NycPlutoAdapter
from opaque_housing.classify.apply import classify_parcel_frame
from opaque_housing.metrics.stock import (
    headline_shares,
    private_residential,
    stock_breakdowns,
    suppress_small,
)
from opaque_housing.schema import OwnerClass

FIXTURE = Path("tests/fixtures/nyc/pluto_sample.csv")
EQUIV = Path("tests/fixtures/nyc/tract_nta_equiv_sample.csv")


def _classified() -> pl.DataFrame:
    adapter = NycPlutoAdapter(snapshot_date=date(2026, 8, 1), tract_equiv_path=EQUIV)
    return classify_parcel_frame(adapter.load_parcels_snapshot(FIXTURE))


def test_fixture_stock_excludes_public_and_keeps_trusts_out_of_headline() -> None:
    classified = _classified()
    private, count = private_residential(classified)
    assert count.rule_id == "exclude_public_nonprofit"
    assert count.rows_out == private.height
    headlines = headline_shares(private)
    entity_only = headlines["private_all_entity_only"]
    with_trust = headlines["private_all_entity_plus_trust"]
    assert entity_only["entity_parcels"] >= 1
    assert classified.filter(pl.col("owner_class") == OwnerClass.TRUST.value).height >= 1
    assert with_trust["entity_parcels"] > entity_only["entity_parcels"]


def test_breakdowns_and_cell_suppression() -> None:
    private, _ = private_residential(_classified())
    tables = stock_breakdowns(private)
    assert {"by_class", "by_building_type", "by_borough_type", "by_nta_type"} <= set(tables)
    assert "suppressed" in tables["by_nta_type"].columns
    forced = tables["by_class"].with_columns(pl.lit(0).alias("units"))
    suppressed = suppress_small(forced)
    assert suppressed["suppressed"].all()
    assert suppressed["unit_share"].null_count() == suppressed.height
