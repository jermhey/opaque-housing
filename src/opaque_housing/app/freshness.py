"""Published freshness plus live Socrata catalog timestamps. No parcel I/O."""

from __future__ import annotations

from typing import Any

from opaque_housing.adapters.cook.sources import SALES as COOK_SALES
from opaque_housing.adapters.cook.sources import UNIVERSE as COOK_UNIVERSE
from opaque_housing.adapters.nyc.sources import PLUTO, TRACT_NTA
from opaque_housing.adapters.soda import fetch_view_meta
from opaque_housing.metros import display_name, laptop_jobs

LIVE_SOURCES: tuple[dict[str, str], ...] = (
    {
        "metro": "nyc",
        "dataset": "pluto",
        "dataset_id": PLUTO.dataset_id,
        "host": "data.cityofnewyork.us",
        "runner": "monthly",
    },
    {
        "metro": "nyc",
        "dataset": "tract_nta",
        "dataset_id": TRACT_NTA.dataset_id,
        "host": "data.cityofnewyork.us",
        "runner": "monthly",
    },
    {
        "metro": "cook",
        "dataset": "universe",
        "dataset_id": COOK_UNIVERSE.dataset_id,
        "host": "datacatalog.cookcountyil.gov",
        "runner": "monthly",
    },
    {
        "metro": "cook",
        "dataset": "sales",
        "dataset_id": COOK_SALES.dataset_id,
        "host": "datacatalog.cookcountyil.gov",
        "runner": "monthly",
    },
)


def live_source_meta(*, fetch: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in LIVE_SOURCES:
        row: dict[str, Any] = {**spec, "rows_updated_at": None, "error": None}
        if fetch:
            try:
                meta = fetch_view_meta(spec["dataset_id"], host=spec["host"])
                row["rows_updated_at"] = meta.get("rows_updated_at")
                row["name"] = meta.get("name")
            except Exception as exc:  # noqa: BLE001 — catalog miss is a freshness note
                row["error"] = str(exc)
        rows.append(row)
    return rows


def freshness_payload(
    documents: dict[str, dict[str, dict[str, Any]]],
    *,
    live: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    published = {metro: docs.get("freshness") or {} for metro, docs in documents.items()}
    return {
        "published": published,
        "live": live or [],
        "laptop_only": [
            *(f"{display_name(metro)} {dataset}" for metro, dataset in laptop_jobs()),
            "Florida DOR SDF (local file; no public URL)",
        ],
        "notes": [
            "GitHub-hosted refresh updates NYC PLUTO, PHL OPA, and Cook stock+sales.",
            "ACRIS, NY DOS, PHL RTT, and Miami-Dade stay laptop-only.",
            "NYC/PHL flow and opacity reuse the last laptop publish. Cook flow is monthly.",
            "Philadelphia Carto has no Socrata rowsUpdatedAt; PHL freshness is last publish.",
            "Florida SDF has no buyer name; Dade entity-buyer shares are unidentified (ADR 0014).",
        ],
    }
