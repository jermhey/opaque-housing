"""Known metro IDs and public labels. Adapters stay metro-specific."""

from __future__ import annotations

from dataclasses import dataclass

METRO_IDS: tuple[str, ...] = ("nyc", "phl", "cook", "dade")

DISPLAY_NAMES: dict[str, str] = {
    "nyc": "New York City",
    "phl": "Philadelphia",
    "cook": "Cook County",
    "dade": "Miami-Dade County",
}

COVERAGE_WINDOWS: dict[str, tuple[int, int]] = {
    "nyc": (2003, 2025),
    "phl": (2000, 2025),
    "cook": (2000, 2025),
    "dade": (2000, 2025),
}

NEIGHBORHOOD_KIND: dict[str, str] = {
    "nyc": "2020 NTA",
    "phl": "ZIP code",
    "cook": "township + assessor neighborhood",
    "dade": "situs ZIP",
}

COMPARE_OTHERS: tuple[str, ...] = ("phl", "cook", "dade")

COMPARE_NOTES: dict[str, str] = {
    "phl": (
        "Philadelphia unit weights are official building-code lower bounds, "
        "not a dwelling census."
    ),
    "cook": (
        "County file, not the City of Chicago. Harmonized sfr_1_4 includes "
        "2–4 unit buildings that are not NYC 1–4 family. Land trusts and "
        "TAXPAYER OF hide beneficial owners."
    ),
    "dade": (
        "County file, not the City of Miami. Harmonized sfr_1_4 includes "
        "2–4 unit buildings that are not NYC 1–4 family. The free Florida "
        "SDF has no buyer name, so entity-buyer shares are not identified."
    ),
}


@dataclass(frozen=True)
class MetroSpec:
    """CLI / app registry row. Adapters stay in their metro packages."""

    metro_id: str
    display_name: str
    neighborhood_kind: str
    coverage_window: tuple[int, int]
    snapshot_date: str
    stock_source: str
    flow_source: str | None
    ingest_kind: str
    opacity: bool = False
    compare_other: bool = False


SPECS: dict[str, MetroSpec] = {
    "nyc": MetroSpec(
        metro_id="nyc",
        display_name=DISPLAY_NAMES["nyc"],
        neighborhood_kind=NEIGHBORHOOD_KIND["nyc"],
        coverage_window=COVERAGE_WINDOWS["nyc"],
        snapshot_date="2026-08-01",
        stock_source="pluto",
        flow_source="acris",
        ingest_kind="soda",
        opacity=True,
    ),
    "phl": MetroSpec(
        metro_id="phl",
        display_name=DISPLAY_NAMES["phl"],
        neighborhood_kind=NEIGHBORHOOD_KIND["phl"],
        coverage_window=COVERAGE_WINDOWS["phl"],
        snapshot_date="2026-04-29",
        stock_source="opa",
        flow_source="rtt",
        ingest_kind="carto",
        compare_other=True,
    ),
    "cook": MetroSpec(
        metro_id="cook",
        display_name=DISPLAY_NAMES["cook"],
        neighborhood_kind=NEIGHBORHOOD_KIND["cook"],
        coverage_window=COVERAGE_WINDOWS["cook"],
        snapshot_date="2026-01-01",
        stock_source="universe",
        flow_source="sales",
        ingest_kind="soda",
        compare_other=True,
    ),
    "dade": MetroSpec(
        metro_id="dade",
        display_name=DISPLAY_NAMES["dade"],
        neighborhood_kind=NEIGHBORHOOD_KIND["dade"],
        coverage_window=COVERAGE_WINDOWS["dade"],
        snapshot_date="2026-01-01",
        stock_source="gis",
        flow_source="sdf",
        ingest_kind="arcgis_or_local",
        compare_other=True,
    ),
}


def display_name(metro: str) -> str:
    return DISPLAY_NAMES.get(metro, metro)


def known_metro(metro: str) -> bool:
    return metro in METRO_IDS


def metro_spec(metro: str) -> MetroSpec:
    spec = SPECS.get(metro)
    if spec is None:
        raise KeyError(metro)
    return spec
