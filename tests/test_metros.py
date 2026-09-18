from opaque_housing.metrics.flow import COOK_SENSITIVITY_CONFIGS, sensitivity_configs_for
from opaque_housing.metros import (
    COMPARE_OTHERS,
    METRO_IDS,
    SPECS,
    default_filename,
    display_name,
    known_metro,
    laptop_jobs,
    metro_spec,
    refresh_metros,
)
from opaque_housing.schema import MetroId


def test_registry_matches_schema() -> None:
    assert set(METRO_IDS) == {item.value for item in MetroId}
    assert set(SPECS) == set(METRO_IDS)
    assert COMPARE_OTHERS == ("phl", "cook", "dade")
    assert display_name("cook") == "Cook County"
    assert display_name("dade") == "Miami-Dade County"
    assert known_metro("cook") is True
    assert known_metro("lax") is False
    cook = metro_spec("cook")
    assert cook.coverage_window == (2000, 2025)
    assert cook.compare_other is True
    assert SPECS["nyc"].opacity is True
    assert SPECS["dade"].opacity is False
    assert SPECS["cook"].refresh_stock is True
    assert SPECS["cook"].refresh_flow is True
    assert SPECS["dade"].refresh_stock is False
    assert SPECS["dade"].require_named_grantee is False
    assert default_filename("cook", "sales") == "wvhk-k5uv.parquet"
    assert refresh_metros() == ("nyc", "phl", "cook")
    assert ("nyc", "acris") in laptop_jobs()
    assert ("dade", "gis") in laptop_jobs()
    assert ("cook", "sales") not in laptop_jobs()
    assert sensitivity_configs_for("cook") == COOK_SENSITIVITY_CONFIGS
    assert sensitivity_configs_for("nyc") is None
