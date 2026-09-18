import polars as pl

from opaque_housing.app.charts import mix_weight_bars, ranked_share_bars, year_sparkline
from opaque_housing.metrics.mix import kitagawa_story, mix_adjust


def _type_table() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "building_type": ["sfr_1_4", "sfr_1_4", "large_mf", "large_mf"],
            "owner_class": ["llc", "individual", "llc", "individual"],
            "class_parcels": [8, 72, 10, 10],
            "class_units": [16, 80, 200, 200],
            "parcels": [80, 80, 20, 20],
            "units": [96, 96, 400, 400],
        }
    )


def _phl_table() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "building_type": ["sfr_1_4", "sfr_1_4", "large_mf", "large_mf"],
            "owner_class": ["llc", "individual", "llc", "individual"],
            "class_parcels": [7, 83, 3, 7],
            "class_units": [10, 90, 40, 60],
            "parcels": [90, 90, 10, 10],
            "units": [100, 100, 100, 100],
        }
    )


def test_kitagawa_story_rate_dominates_fixture() -> None:
    mix = mix_adjust(_type_table(), _phl_table(), weight="parcel")
    story = kitagawa_story(mix)
    assert story["dominant"] == "rate"
    assert story["rate_share"] + story["mix_share"] == 1


def test_mix_weight_bars_use_percent_widths() -> None:
    bars = mix_weight_bars(
        [
            {
                "building_type": "sfr_1_4",
                "reference_weight": 0.8,
                "other_weight": 0.5,
            }
        ]
    )
    assert bars[0]["label"] == "1–4 family (harmonized)"
    assert bars[0]["reference_width"] == 80
    assert bars[0]["other_width"] == 50


def test_ranked_share_bars_drop_suppressed_and_sort() -> None:
    bars = ranked_share_bars(
        [
            {"nta_name": "Low", "entity_parcel_share": 0.1, "suppressed": False},
            {"nta_name": "High", "entity_parcel_share": 0.4, "suppressed": "false"},
            {"nta_name": "Hidden", "entity_parcel_share": 0.9, "suppressed": True},
        ]
    )
    assert [row["label"] for row in bars] == ["High", "Low"]
    assert bars[0]["width"] == 100


def test_year_sparkline_needs_two_points() -> None:
    assert year_sparkline([{"year": 2024, "sale_share": 0.2}]) is None
    chart = year_sparkline(
        [
            {"year": 2023, "sale_share": 0.1},
            {"year": 2024, "sale_share": 0.2},
        ]
    )
    assert chart is not None
    assert chart["path"].startswith("M ")
    assert "L " in chart["path"]
    assert chart["first_year"] == 2023
    assert chart["end"] == 0.2
