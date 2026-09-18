import polars as pl
import pytest

from opaque_housing.metrics.concentration import CONCENTRATION_COLUMNS, neighborhood_concentration
from opaque_housing.metrics.publish import forbidden_columns


def _parcels() -> pl.DataFrame:
    rows = []
    for i in range(50):
        rows.append(
            {
                "parcel_id": f"A{i}",
                "geo_neighborhood": "NTA1",
                "owner_key": "big",
                "res_units": 1,
            }
        )
    for i in range(30):
        rows.append(
            {
                "parcel_id": f"B{i}",
                "geo_neighborhood": "NTA1",
                "owner_key": "mid",
                "res_units": 1,
            }
        )
    for i in range(20):
        rows.append(
            {
                "parcel_id": f"C{i}",
                "geo_neighborhood": "NTA1",
                "owner_key": "small",
                "res_units": 1,
            }
        )
    for i in range(3):
        rows.append(
            {
                "parcel_id": f"T{i}",
                "geo_neighborhood": "TINY",
                "owner_key": "solo",
                "res_units": 1,
            }
        )
    return pl.DataFrame(rows)


def test_neighborhood_hhi_and_topn() -> None:
    table = neighborhood_concentration(_parcels(), min_units=10)
    large = table.filter(pl.col("geo_neighborhood") == "NTA1").row(0, named=True)
    tiny = table.filter(pl.col("geo_neighborhood") == "TINY").row(0, named=True)
    assert large["n_name_keys"] == 3
    assert large["hhi_units"] == pytest.approx(0.5**2 + 0.3**2 + 0.2**2)
    assert large["top5_unit_share"] == pytest.approx(1.0)
    assert large["top5_parcel_share"] == pytest.approx(1.0)
    assert large["suppressed"] is False
    assert tiny["suppressed"] is True
    assert tiny["hhi_units"] is None
    assert set(table.columns) == set(CONCENTRATION_COLUMNS)
    assert forbidden_columns(table.columns) == []


def test_blank_keys_are_not_merged() -> None:
    frame = pl.DataFrame(
        {
            "parcel_id": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            "geo_neighborhood": ["Z"] * 10,
            "owner_key": [""] * 10,
            "res_units": [1] * 10,
        }
    )
    table = neighborhood_concentration(frame, min_units=10)
    row = table.row(0, named=True)
    assert row["n_name_keys"] == 10
    assert row["hhi_units"] == pytest.approx(10 * (0.1**2))
