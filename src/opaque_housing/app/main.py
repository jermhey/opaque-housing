"""FastAPI insight app. Loads allowlisted published files only."""

from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from opaque_housing.app.routes_admin import router as admin_router
from opaque_housing.app.routes_pages import router as pages_router
from opaque_housing.app.routes_v1 import router as v1_router
from opaque_housing.app.security import session_secret
from opaque_housing.app.store import AggregateStore
from opaque_housing.app.sync import reload_store
from opaque_housing.metrics.publish import PublishError
from opaque_housing.paths import data_root

STATIC_DIR = Path(__file__).parent / "static"


def published_root_from_env(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    env = os.environ.get("OH_PUBLISHED_DIR")
    if env:
        return Path(env)
    return data_root() / "published"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    store = application.state.store
    if _truthy(os.environ.get("OH_SYNC_ON_BOOT")):
        try:
            application.state.last_sync = reload_store(store)
        except Exception as exc:  # noqa: BLE001 — boot keeps the image snapshot
            application.state.last_sync = {"ok": False, "error": str(exc)}
    yield


def create_app(published_root: Path | None = None) -> FastAPI:
    store = AggregateStore(published_root_from_env(published_root))
    application = FastAPI(
        title="Opaque housing insight API",
        description=(
            "Public aggregates only. There is no address, name, BBL, or OPA-account search. "
            "The pipeline (`oh publish`) is the source of truth."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.store = store
    application.state.last_sync = None
    application.add_middleware(SessionMiddleware, secret_key=session_secret())
    if STATIC_DIR.exists():
        application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    application.include_router(v1_router, prefix="/v1")
    application.include_router(admin_router, prefix="/admin", include_in_schema=False)
    application.include_router(pages_router, include_in_schema=False)

    @application.post("/internal/reload", include_in_schema=False)
    def internal_reload(request: Request) -> dict[str, Any]:
        expected = os.environ.get("OH_SYNC_TOKEN")
        if not expected:
            raise HTTPException(status_code=503, detail="OH_SYNC_TOKEN is not set")
        header = request.headers.get("authorization", "")
        token = header.removeprefix("Bearer ").strip()
        if not token or not secrets.compare_digest(token, expected):
            raise HTTPException(status_code=401, detail="invalid sync token")
        current = request.app.state.store
        if not isinstance(current, AggregateStore):
            raise RuntimeError("aggregate store is not configured")
        return reload_store(current)

    @application.exception_handler(PublishError)
    async def _publish_error(_request: Request, exc: PublishError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=500)

    return application


app = create_app()
