"""JSON payloads over the allowlisted store. Pure besides store reads."""

from __future__ import annotations

from typing import Any

from opaque_housing.app.store import AggregateStore
from opaque_housing.metrics.claims import flow_claim, stock_claim, stock_sensitivity_table
from opaque_housing.metrics.flow import COVERAGE_WINDOWS
from opaque_housing.metrics.mix import mix_adjust
from opaque_housing.metrics.publish import FORBIDDEN_COLUMNS, PublishError, assert_safe_columns


def assert_payload_safe(payload: object, *, origin: str) -> None:
    keys = _keys(payload)
    leaked = sorted({key for key in keys if key.lower() in FORBIDDEN_COLUMNS})
    if leaked:
        raise PublishError(f"{origin} leaked unpublished columns: {', '.join(leaked)}")


def _keys(payload: object) -> list[str]:
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                found.add(str(key))
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def _filters(store: AggregateStore, metro: str) -> list[dict[str, Any]]:
    manifest = store.document(metro, "run_manifest") or {}
    raw = manifest.get("filter_counts")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _window(metro: str) -> str:
    start, end = COVERAGE_WINDOWS.get(metro, (None, None))
    if start is None or end is None:
        return ""
    return f"{start}–{end}"


def stock_payload(store: AggregateStore, metro: str) -> dict[str, Any]:
    headlines = store.document(metro, "headlines") or {}
    payload = {
        "metro": metro,
        "headlines": headlines,
        "stock_by_class": store.frame(metro, "stock_by_class").to_dicts(),
        "stock_by_building_type": store.frame(metro, "stock_by_building_type").to_dicts(),
        "stock_sensitivity": _stock_sensitivity(store, metro, headlines),
    }
    assert_payload_safe(payload, origin=f"/v1/{metro}/stock")
    return payload


def _stock_sensitivity(
    store: AggregateStore, metro: str, headlines: dict[str, Any]
) -> list[dict[str, Any]]:
    if store.has_table(metro, "stock_sensitivity"):
        table = store.frame(metro, "stock_sensitivity")
        assert_safe_columns(table.columns, origin=f"{metro}/stock_sensitivity")
        return table.to_dicts()
    return stock_sensitivity_table(headlines).to_dicts()


def flow_payload(store: AggregateStore, metro: str) -> dict[str, Any]:
    payload = {
        "metro": metro,
        "window": {"start": COVERAGE_WINDOWS[metro][0], "end": COVERAGE_WINDOWS[metro][1]}
        if metro in COVERAGE_WINDOWS
        else {},
        "headlines": store.document(metro, "flow_headlines") or {},
        "by_year": store.frame(metro, "flow_by_year").to_dicts(),
        "sfr_condo": store.frame(metro, "flow_sfr_condo_by_year").to_dicts(),
        "sensitivity": store.frame(metro, "flow_sensitivity").to_dicts(),
    }
    assert_payload_safe(payload, origin=f"/v1/{metro}/flow")
    return payload


def neighborhoods_payload(store: AggregateStore, metro: str) -> dict[str, Any]:
    payload = {
        "metro": metro,
        "neighborhoods": store.frame(metro, "neighborhoods").to_dicts(),
        "concentration": store.frame(metro, "concentration_by_neighborhood").to_dicts(),
        "has_concentration": store.has_table(metro, "concentration_by_neighborhood"),
        "caveat": (
            "HHI is of recorded name-keys, not the opacity graph. "
            "Citywide top-portfolio lists are not published: cluster 1 is a known "
            "likely false merge (docs/milestones/m3-llm-and-opacity.md)."
        ),
    }
    assert_payload_safe(payload, origin=f"/v1/{metro}/neighborhoods")
    return payload


def mix_payload(store: AggregateStore, *, weight: str = "parcel") -> dict[str, Any]:
    nyc = store.frame("nyc", "stock_by_building_type")
    phl = store.frame("phl", "stock_by_building_type")
    mixed = mix_adjust(nyc, phl, weight=weight)
    nyc_head = store.document("nyc", "headlines") or {}
    phl_head = store.document("phl", "headlines") or {}
    payload = {
        "weight": weight,
        "mix": mixed,
        "nyc_claim": stock_claim(
            nyc_head,
            series="private_all",
            weight=weight,
            include_trust=False,
            window="current snapshot",
            filters=_filters(store, "nyc"),
        )
        if nyc_head
        else None,
        "phl_claim": stock_claim(
            phl_head,
            series="private_all",
            weight=weight,
            include_trust=False,
            window="current snapshot",
            filters=_filters(store, "phl"),
        )
        if phl_head
        else None,
    }
    assert_payload_safe(payload, origin="/v1/compare/mix")
    return payload


def definition_payload(
    store: AggregateStore,
    metro: str,
    *,
    series: str,
    weight: str,
    include_trust: bool,
    flow_config: str,
    flow_weight: str,
) -> dict[str, Any]:
    headlines = store.document(metro, "headlines") or {}
    sensitivity = store.frame(metro, "flow_sensitivity")
    extra = ""
    if metro == "phl":
        extra = "Philadelphia window is 2000–2025. Sheriff deeds are in the default series."
    elif metro == "nyc":
        extra = "NYC window is 2003–2025 (ADR 0006)."
    stock = None
    if headlines:
        try:
            stock = stock_claim(
                headlines,
                series=series,
                weight=weight,
                include_trust=include_trust,
                window="current snapshot",
                filters=_filters(store, metro),
            )
        except KeyError:
            stock = None
    payload = {
        "metro": metro,
        "stock": stock,
        "flow": None,
    }
    if not sensitivity.is_empty() and "config" in sensitivity.columns:
        configs = set(sensitivity["config"].to_list())
        if flow_config in configs:
            payload["flow"] = flow_claim(
                sensitivity,
                config=flow_config,
                weight=flow_weight,
                window=_window(metro),
                extra_caveat=extra,
            )
    assert_payload_safe(payload, origin=f"/v1/{metro}/definition")
    return payload
