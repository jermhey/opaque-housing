import polars as pl
import pytest

from opaque_housing.metrics.claims import flow_claim, stock_claim, stock_sensitivity_table


def _headlines() -> dict:
    return {
        "private_all_entity_only": {
            "parcels": 100,
            "units": 200,
            "entity_parcels": 10,
            "entity_units": 40,
            "parcel_share": 0.1,
            "unit_share": 0.2,
        },
        "private_all_entity_plus_trust": {
            "parcels": 100,
            "units": 200,
            "entity_parcels": 15,
            "entity_units": 50,
            "parcel_share": 0.15,
            "unit_share": 0.25,
        },
        "sfr_condo_entity_only": {
            "parcels": 80,
            "units": 90,
            "entity_parcels": 8,
            "entity_units": 9,
            "parcel_share": 0.1,
            "unit_share": 0.1,
        },
        "sfr_condo_entity_plus_trust": {
            "parcels": 80,
            "units": 90,
            "entity_parcels": 12,
            "entity_units": 14,
            "parcel_share": 0.15,
            "unit_share": 0.155,
        },
        "correction": {
            "private_all_entity_only": {
                "parcel": {
                    "corrected": 0.09,
                    "corrected_lo": 0.07,
                    "corrected_hi": 0.11,
                    "n_labeled": 10,
                }
            }
        },
    }


def test_stock_claim_uses_correction() -> None:
    card = stock_claim(_headlines(), series="private_all", weight="parcel", include_trust=False)
    assert card["raw"] == pytest.approx(0.1)
    assert card["corrected"] == pytest.approx(0.09)
    assert card["n_labeled"] == 10
    assert "entity only" in card["caveat"]


def test_stock_sensitivity_has_eight_rows() -> None:
    table = stock_sensitivity_table(_headlines())
    assert table.height == 8
    trust = table.filter((pl.col("include_trust")) & (pl.col("weight") == "parcel"))
    assert trust.height == 2


def test_flow_claim_reads_sensitivity() -> None:
    table = pl.DataFrame(
        {
            "config": ["default_10k", "exclude_sheriff"],
            "min_consideration": [10000.0, 10000.0],
            "sales": [100, 80],
            "entity_sales": [20, 12],
            "sale_share": [0.2, 0.15],
            "units": [200, 160],
            "entity_units": [50, 30],
            "unit_share": [0.25, 0.1875],
        }
    )
    card = flow_claim(table, config="exclude_sheriff", weight="sale")
    assert card["raw"] == pytest.approx(0.15)
    assert card["sales"] == 80
