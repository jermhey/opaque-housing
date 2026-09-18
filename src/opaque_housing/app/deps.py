"""Request helpers."""

from __future__ import annotations

from fastapi import HTTPException, Request

from opaque_housing.app.store import AggregateStore


def get_store(request: Request) -> AggregateStore:
    store = request.app.state.store
    if not isinstance(store, AggregateStore):
        raise RuntimeError("aggregate store is not configured")
    return store


def require_metro(store: AggregateStore, metro: str) -> str:
    if not store.has_metro(metro):
        raise HTTPException(status_code=404, detail=f"unknown metro {metro}")
    return metro
