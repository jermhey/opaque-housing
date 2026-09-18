from opaque_housing.metros import (
    COMPARE_OTHERS,
    METRO_IDS,
    SPECS,
    display_name,
    known_metro,
    metro_spec,
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
