"""HTMX pages. Same visual language as the static snapshot."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from opaque_housing.app.deps import get_store, require_metro
from opaque_housing.app.formatters import claim_display, intcomma, pct
from opaque_housing.app.payloads import (
    definition_payload,
    flow_payload,
    mix_payload,
    neighborhoods_payload,
)
from opaque_housing.app.store import AggregateStore
from opaque_housing.app.templating import render

router = APIRouter()


def _ctx(**extra: object) -> dict[str, object]:
    return {"pct": pct, "intcomma": intcomma, **extra}


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    store: Annotated[AggregateStore, Depends(get_store)],
    weight: Annotated[str, Query(pattern="^(parcel|unit)$")] = "parcel",
) -> HTMLResponse:
    mixed = None
    if "nyc" in store.metros and "phl" in store.metros:
        mixed = mix_payload(store, weight=weight)
        if mixed.get("nyc_claim"):
            mixed["nyc_claim"] = claim_display(mixed["nyc_claim"])
        if mixed.get("phl_claim"):
            mixed["phl_claim"] = claim_display(mixed["phl_claim"])
    return render(
        request,
        "home.html",
        _ctx(page="home", weight=weight, mixed=mixed, metros=store.metros),
    )


@router.get("/partials/mix", response_class=HTMLResponse)
def mix_partial(
    request: Request,
    store: Annotated[AggregateStore, Depends(get_store)],
    weight: Annotated[str, Query(pattern="^(parcel|unit)$")] = "parcel",
) -> HTMLResponse:
    mixed = mix_payload(store, weight=weight)
    if mixed.get("nyc_claim"):
        mixed["nyc_claim"] = claim_display(mixed["nyc_claim"])
    if mixed.get("phl_claim"):
        mixed["phl_claim"] = claim_display(mixed["phl_claim"])
    return render(request, "partials/mix.html", _ctx(weight=weight, mixed=mixed), partial=True)


@router.get("/neighborhoods", response_class=HTMLResponse)
def neighborhoods(
    request: Request,
    store: Annotated[AggregateStore, Depends(get_store)],
    metro: str = "nyc",
) -> HTMLResponse:
    require_metro(store, metro)
    payload = neighborhoods_payload(store, metro)
    return render(
        request,
        "neighborhoods.html",
        _ctx(page="neighborhoods", metro=metro, metros=store.metros, data=payload),
    )


@router.get("/partials/neighborhoods", response_class=HTMLResponse)
def neighborhoods_partial(
    request: Request,
    store: Annotated[AggregateStore, Depends(get_store)],
    metro: str = "nyc",
) -> HTMLResponse:
    require_metro(store, metro)
    payload = neighborhoods_payload(store, metro)
    return render(
        request,
        "partials/neighborhoods.html",
        _ctx(metro=metro, data=payload),
        partial=True,
    )


@router.get("/definitions", response_class=HTMLResponse)
def definitions(
    request: Request,
    store: Annotated[AggregateStore, Depends(get_store)],
    metro: str = "nyc",
    series: Annotated[str, Query(pattern="^(private_all|sfr_condo)$")] = "private_all",
    weight: Annotated[str, Query(pattern="^(parcel|unit)$")] = "parcel",
    include_trust: bool = False,
    flow_config: str = "default_10k",
    flow_weight: Annotated[str, Query(pattern="^(sale|unit)$")] = "sale",
) -> HTMLResponse:
    require_metro(store, metro)
    payload = definition_payload(
        store,
        metro,
        series=series,
        weight=weight,
        include_trust=include_trust,
        flow_config=flow_config,
        flow_weight=flow_weight,
    )
    if payload.get("stock"):
        payload["stock"] = claim_display(payload["stock"])
    if payload.get("flow"):
        payload["flow"] = claim_display(payload["flow"])
    flow_configs = []
    sensitivity = store.frame(metro, "flow_sensitivity")
    if not sensitivity.is_empty() and "config" in sensitivity.columns:
        flow_configs = sorted(str(item) for item in sensitivity["config"].unique().to_list())
    return render(
        request,
        "definitions.html",
        _ctx(
            page="definitions",
            metro=metro,
            metros=store.metros,
            series=series,
            weight=weight,
            include_trust=include_trust,
            flow_config=flow_config,
            flow_weight=flow_weight,
            flow_configs=flow_configs,
            data=payload,
        ),
    )


@router.get("/partials/definition", response_class=HTMLResponse)
def definition_partial(
    request: Request,
    store: Annotated[AggregateStore, Depends(get_store)],
    metro: str = "nyc",
    series: Annotated[str, Query(pattern="^(private_all|sfr_condo)$")] = "private_all",
    weight: Annotated[str, Query(pattern="^(parcel|unit)$")] = "parcel",
    include_trust: bool = False,
    flow_config: str = "default_10k",
    flow_weight: Annotated[str, Query(pattern="^(sale|unit)$")] = "sale",
) -> HTMLResponse:
    require_metro(store, metro)
    payload = definition_payload(
        store,
        metro,
        series=series,
        weight=weight,
        include_trust=include_trust,
        flow_config=flow_config,
        flow_weight=flow_weight,
    )
    if payload.get("stock"):
        payload["stock"] = claim_display(payload["stock"])
    if payload.get("flow"):
        payload["flow"] = claim_display(payload["flow"])
    return render(request, "partials/claims.html", _ctx(data=payload), partial=True)


@router.get("/trends", response_class=HTMLResponse)
def trends(
    request: Request,
    store: Annotated[AggregateStore, Depends(get_store)],
    metro: str = "nyc",
) -> HTMLResponse:
    require_metro(store, metro)
    return render(
        request,
        "trends.html",
        _ctx(page="trends", metro=metro, metros=store.metros, data=flow_payload(store, metro)),
    )


@router.get("/freshness", response_class=HTMLResponse)
def freshness_page(
    request: Request,
    store: Annotated[AggregateStore, Depends(get_store)],
    live: bool = False,
) -> HTMLResponse:
    from opaque_housing.app.freshness import freshness_payload, live_source_meta

    payload = freshness_payload(store.documents, live=live_source_meta(fetch=live))
    return render(request, "freshness.html", _ctx(page="freshness", data=payload, live=live))


@router.get("/methodology", response_class=HTMLResponse)
def methodology(request: Request) -> HTMLResponse:
    return render(request, "methodology.html", _ctx(page="methodology"))


@router.get("/limitations", response_class=HTMLResponse)
def limitations(request: Request) -> HTMLResponse:
    return render(request, "limitations.html", _ctx(page="limitations"))


@router.get("/data", response_class=HTMLResponse)
def downloads(
    request: Request,
    store: Annotated[AggregateStore, Depends(get_store)],
) -> HTMLResponse:
    files = {metro: sorted(store.tables.get(metro, set())) for metro in store.metros}
    return render(request, "data.html", _ctx(page="data", files=files, metros=store.metros))
