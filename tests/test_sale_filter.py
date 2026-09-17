from pathlib import Path

from opaque_housing.adapters.nyc.acris import NycAcrisAdapter
from opaque_housing.metrics.sale_filter import (
    SaleFilterConfig,
    apply_sale_filter,
    attach_primary_parties,
    family_token,
    same_surname,
)

MASTER = Path("tests/fixtures/nyc/acris_master.csv")
LEGALS = Path("tests/fixtures/nyc/acris_legals.csv")
PARTIES = Path("tests/fixtures/nyc/acris_parties.csv")


def _transfers():
    adapter = NycAcrisAdapter()
    transfers = adapter.load_transfers(MASTER, LEGALS)
    parties = adapter.load_transfer_parties(PARTIES)
    return attach_primary_parties(transfers, parties)


def test_default_filter_keeps_named_sales_above_10k() -> None:
    kept, counts = apply_sale_filter(_transfers())
    ids = set(kept["doc_id"].to_list())
    assert ids == {
        "D2004SALE",
        "D2015LLC",
        "D2018FAM",
        "D2020CONDO",
        "D2020MULTI",
        "D2021PART",
    }
    assert {item.rule_id for item in counts} >= {
        "sale_deed_type",
        "named_grantee",
        "min_consideration",
    }
    assert "D2015ZERO" not in ids
    assert "D2015LOW" not in ids
    assert "D2016CORR" not in ids
    assert "D2024NONE" not in ids


def test_zero_as_missing_keeps_zero_amount_deed() -> None:
    kept, _ = apply_sale_filter(
        _transfers(),
        SaleFilterConfig(treat_zero_amount_as_missing=True),
    )
    assert "D2015ZERO" in set(kept["doc_id"].to_list())
    assert "D2015LOW" not in set(kept["doc_id"].to_list())


def test_threshold_zero_keeps_low_and_zero() -> None:
    kept, _ = apply_sale_filter(_transfers(), SaleFilterConfig(min_consideration=0.0))
    ids = set(kept["doc_id"].to_list())
    assert "D2015ZERO" in ids
    assert "D2015LOW" in ids


def test_require_full_interest_drops_partial() -> None:
    kept, counts = apply_sale_filter(
        _transfers(),
        SaleFilterConfig(require_full_interest=True),
    )
    assert "D2021PART" not in set(kept["doc_id"].to_list())
    assert any(item.rule_id == "full_interest" for item in counts)


def test_same_surname_exclusion() -> None:
    assert family_token("SMITH, JOHN") == "SMITH"
    assert same_surname("SMITH JOHN", "SMITH MARY") is True
    kept, _ = apply_sale_filter(
        _transfers(),
        SaleFilterConfig(exclude_same_surname=True),
    )
    assert "D2018FAM" not in set(kept["doc_id"].to_list())


def test_drop_astu() -> None:
    kept, _ = apply_sale_filter(
        _transfers(),
        SaleFilterConfig(drop_sale_codes=frozenset({"ASTU"})),
    )
    assert "D2020CONDO" not in set(kept["doc_id"].to_list())
