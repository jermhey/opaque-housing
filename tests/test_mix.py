import polars as pl
import pytest

from opaque_housing.metrics.mix import building_type_entity_rates, mix_adjust


def _type_table() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "building_type": [
                "sfr_1_4",
                "sfr_1_4",
                "large_mf",
                "large_mf",
            ],
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
            "building_type": [
                "sfr_1_4",
                "sfr_1_4",
                "large_mf",
                "large_mf",
            ],
            "owner_class": ["llc", "individual", "llc", "individual"],
            "class_parcels": [7, 83, 3, 7],
            "class_units": [10, 90, 40, 60],
            "parcels": [90, 90, 10, 10],
            "units": [100, 100, 100, 100],
        }
    )


def test_type_rates_entity_only() -> None:
    rates = building_type_entity_rates(_type_table())
    sfr = rates.filter(pl.col("building_type") == "sfr_1_4").row(0, named=True)
    assert sfr["parcel_rate"] == pytest.approx(0.1)
    assert sfr["parcel_weight"] == pytest.approx(0.8)


def test_mix_adjust_kitagawa_adds_up() -> None:
    result = mix_adjust(_type_table(), _phl_table(), weight="parcel")
    assert result["nyc_observed"] == pytest.approx(0.18)
    assert result["phl_observed"] == pytest.approx(0.10)
    assert result["phl_on_nyc_mix"] == pytest.approx(0.8 * (7 / 90) + 0.2 * 0.3)
    assert result["gap_common"] == pytest.approx(result["rate_effect"] + result["mix_effect"])
    assert result["phl_on_nyc_mix"] == pytest.approx(
        result["phl_observed_common"] + result["mix_effect"]
    )
    assert "coop_building" not in result["common_types"]


def test_mix_adjust_rejects_bad_weight() -> None:
    with pytest.raises(ValueError, match="weight"):
        mix_adjust(_type_table(), _phl_table(), weight="lots")


def test_mix_adjust_generic_ids() -> None:
    result = mix_adjust(
        _type_table(),
        _phl_table(),
        weight="parcel",
        reference_id="nyc",
        other_id="cook",
    )
    assert result["reference_id"] == "nyc"
    assert result["other_id"] == "cook"
    assert result["nyc_observed"] == pytest.approx(result["reference_observed"])
    assert result["cook_observed"] == pytest.approx(result["other_observed"])
    assert result["gap_common"] == pytest.approx(result["rate_effect"] + result["mix_effect"])
