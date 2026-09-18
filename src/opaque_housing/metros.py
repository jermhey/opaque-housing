"""Known metro IDs and public labels. Adapters stay metro-specific."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opaque_housing.paths import latest_raw_file


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
    stock_datasets: tuple[str, ...]
    default_files: tuple[tuple[str, str], ...]
    window_note: str
    compare_note: str = ""
    flow_datasets: tuple[str, ...] = ()
    laptop_datasets: tuple[str, ...] = ()
    sensitivity_profile: str = "nyc"
    require_named_grantee: bool = True
    refresh_stock: bool = False
    refresh_flow: bool = False
    opacity: bool = False
    compare_other: bool = False


SPECS: dict[str, MetroSpec] = {
    "nyc": MetroSpec(
        metro_id="nyc",
        display_name="New York City",
        neighborhood_kind="2020 NTA",
        coverage_window=(2003, 2025),
        snapshot_date="2026-08-01",
        stock_source="pluto",
        flow_source="acris",
        ingest_kind="soda",
        stock_datasets=("pluto", "tract_nta"),
        flow_datasets=("acris_master", "acris_legals", "acris_parties"),
        laptop_datasets=("acris", "opacity"),
        default_files=(
            ("pluto", "64uk-42ks.csv"),
            ("tract_nta", "hm78-6dwm.csv"),
            ("acris_master", "bnx9-e6tj.parquet"),
            ("acris_legals", "8h5j-fqxa.parquet"),
            ("acris_parties", "636b-3b5g.parquet"),
            ("hpd_registrations", "tesw-yqqr.csv"),
            ("hpd_contacts", "feu5-w2e2.csv"),
            ("nys_dos", "n9v6-gdp6.parquet"),
        ),
        window_note="coverage window recorded years 2003-2025 (ADR 0006)",
        sensitivity_profile="nyc",
        refresh_stock=True,
        opacity=True,
    ),
    "phl": MetroSpec(
        metro_id="phl",
        display_name="Philadelphia",
        neighborhood_kind="ZIP code",
        coverage_window=(2000, 2025),
        snapshot_date="2026-04-29",
        stock_source="opa",
        flow_source="rtt",
        ingest_kind="carto",
        stock_datasets=("opa",),
        flow_datasets=("rtt",),
        laptop_datasets=("rtt",),
        default_files=(
            ("opa", "opa_properties_public.csv"),
            ("rtt", "rtt_summary.csv"),
        ),
        window_note="coverage window recorded years 2000-2025 (ADR 0010)",
        compare_note=(
            "Philadelphia unit weights are official building-code lower bounds, "
            "not a dwelling census."
        ),
        sensitivity_profile="phl",
        refresh_stock=True,
        compare_other=True,
    ),
    "cook": MetroSpec(
        metro_id="cook",
        display_name="Cook County",
        neighborhood_kind="township + assessor neighborhood",
        coverage_window=(2000, 2025),
        snapshot_date="2026-01-01",
        stock_source="universe",
        flow_source="sales",
        ingest_kind="soda",
        stock_datasets=("universe", "addresses", "characteristics", "condo"),
        flow_datasets=("sales",),
        default_files=(
            ("universe", "pabr-t5kh.parquet"),
            ("addresses", "3723-97qp.parquet"),
            ("characteristics", "x54s-btds.parquet"),
            ("condo", "3r7i-mrz4.parquet"),
            ("sales", "wvhk-k5uv.parquet"),
        ),
        window_note="coverage window recorded years 2000-2025 (ADR 0013)",
        compare_note=(
            "County file, not the City of Chicago. Harmonized sfr_1_4 includes "
            "2–4 unit buildings that are not NYC 1–4 family. Land trusts and "
            "TAXPAYER OF hide beneficial owners."
        ),
        sensitivity_profile="cook",
        refresh_stock=True,
        refresh_flow=True,
        compare_other=True,
    ),
    "dade": MetroSpec(
        metro_id="dade",
        display_name="Miami-Dade County",
        neighborhood_kind="situs ZIP",
        coverage_window=(2000, 2025),
        snapshot_date="2026-01-01",
        stock_source="gis",
        flow_source="sdf",
        ingest_kind="arcgis_or_local",
        stock_datasets=("gis",),
        flow_datasets=("sdf",),
        laptop_datasets=("gis",),
        default_files=(
            ("gis", "pagis_property.parquet"),
            ("sdf", "florida_sdf.csv"),
        ),
        window_note="coverage window recorded years 2000-2025; SDF has no grantee (ADR 0014)",
        compare_note=(
            "County file, not the City of Miami. Harmonized sfr_1_4 includes "
            "2–4 unit buildings that are not NYC 1–4 family. The free Florida "
            "SDF has no buyer name, so entity-buyer shares are not identified."
        ),
        sensitivity_profile="dade",
        require_named_grantee=False,
        compare_other=True,
    ),
}

METRO_IDS: tuple[str, ...] = tuple(SPECS)
DISPLAY_NAMES: dict[str, str] = {key: spec.display_name for key, spec in SPECS.items()}
COVERAGE_WINDOWS: dict[str, tuple[int, int]] = {
    key: spec.coverage_window for key, spec in SPECS.items()
}
NEIGHBORHOOD_KIND: dict[str, str] = {
    key: spec.neighborhood_kind for key, spec in SPECS.items()
}
COMPARE_OTHERS: tuple[str, ...] = tuple(
    key for key, spec in SPECS.items() if spec.compare_other
)
COMPARE_NOTES: dict[str, str] = {
    key: spec.compare_note for key, spec in SPECS.items() if spec.compare_note
}


def display_name(metro: str) -> str:
    spec = SPECS.get(metro)
    return spec.display_name if spec else metro


def known_metro(metro: str) -> bool:
    return metro in SPECS


def metro_spec(metro: str) -> MetroSpec:
    spec = SPECS.get(metro)
    if spec is None:
        raise KeyError(metro)
    return spec


def default_filename(metro: str, dataset: str) -> str:
    for name, filename in metro_spec(metro).default_files:
        if name == dataset:
            return filename
    raise KeyError(dataset)


def latest_dataset(metro: str, dataset: str) -> Path | None:
    return latest_raw_file(metro, dataset, default_filename(metro, dataset))


def refresh_metros(*, flow: bool = False) -> tuple[str, ...]:
    return tuple(
        key
        for key, spec in SPECS.items()
        if (spec.refresh_flow if flow else spec.refresh_stock)
    )


def laptop_jobs() -> tuple[tuple[str, str], ...]:
    jobs: list[tuple[str, str]] = []
    for key, spec in SPECS.items():
        for dataset in spec.laptop_datasets:
            jobs.append((key, dataset))
    return tuple(jobs)
