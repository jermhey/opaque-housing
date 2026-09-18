"""Public JSON API. Allowlisted aggregates only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from opaque_housing.app.deps import get_store, require_metro
from opaque_housing.app.freshness import freshness_payload, live_source_meta
from opaque_housing.app.payloads import (
    definition_payload,
    flow_payload,
    mix_payload,
    neighborhoods_payload,
    stock_payload,
)
from opaque_housing.app.store import AggregateStore

router = APIRouter(tags=["v1"])


@router.get("/metros")
def metros(store: Annotated[AggregateStore, Depends(get_store)]) -> dict[str, object]:
    return {"metros": store.metros}


@router.get("/compare/mix")
def compare_mix(
    store: Annotated[AggregateStore, Depends(get_store)],
    weight: Annotated[str, Query(pattern="^(parcel|unit)$")] = "parcel",
) -> dict[str, object]:
    if "nyc" not in store.metros or "phl" not in store.metros:
        raise HTTPException(status_code=404, detail="both nyc and phl aggregates are required")
    return mix_payload(store, weight=weight)


@router.get("/freshness")
def freshness(
    store: Annotated[AggregateStore, Depends(get_store)],
    live: bool = False,
) -> dict[str, object]:
    return freshness_payload(store.documents, live=live_source_meta(fetch=live))


@router.get("/{metro}/stock")
def stock(
    metro: str,
    store: Annotated[AggregateStore, Depends(get_store)],
) -> dict[str, object]:
    return stock_payload(store, require_metro(store, metro))


@router.get("/{metro}/flow")
def flow(
    metro: str,
    store: Annotated[AggregateStore, Depends(get_store)],
) -> dict[str, object]:
    return flow_payload(store, require_metro(store, metro))


@router.get("/{metro}/neighborhoods")
def neighborhoods(
    metro: str,
    store: Annotated[AggregateStore, Depends(get_store)],
) -> dict[str, object]:
    return neighborhoods_payload(store, require_metro(store, metro))


@router.get("/{metro}/definition")
def definition(
    metro: str,
    store: Annotated[AggregateStore, Depends(get_store)],
    series: Annotated[str, Query(pattern="^(private_all|sfr_condo)$")] = "private_all",
    weight: Annotated[str, Query(pattern="^(parcel|unit)$")] = "parcel",
    include_trust: bool = False,
    flow_config: str = "default_10k",
    flow_weight: Annotated[str, Query(pattern="^(sale|unit)$")] = "sale",
) -> dict[str, object]:
    return definition_payload(
        store,
        require_metro(store, metro),
        series=series,
        weight=weight,
        include_trust=include_trust,
        flow_config=flow_config,
        flow_weight=flow_weight,
    )


@router.get("/{metro}/freshness")
def metro_freshness(
    metro: str,
    store: Annotated[AggregateStore, Depends(get_store)],
) -> dict[str, object]:
    require_metro(store, metro)
    docs = store.document(metro, "freshness") or {}
    return {"metro": metro, "freshness": docs}
