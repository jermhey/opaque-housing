"""FastAPI insight app. Loads allowlisted published files only."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from opaque_housing.app.routes_admin import router as admin_router
from opaque_housing.app.routes_pages import router as pages_router
from opaque_housing.app.routes_v1 import router as v1_router
from opaque_housing.app.security import session_secret
from opaque_housing.app.store import AggregateStore
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


def create_app(published_root: Path | None = None) -> FastAPI:
    store = AggregateStore(published_root_from_env(published_root))
    application = FastAPI(
        title="Opaque housing insight API",
        description=(
            "Public aggregates only. There is no address, name, BBL, or OPA-account search. "
            "The pipeline (`oh publish`) is the source of truth."
        ),
        version="0.1.0",
    )
    application.state.store = store
    application.add_middleware(SessionMiddleware, secret_key=session_secret())
    if STATIC_DIR.exists():
        application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    application.include_router(v1_router, prefix="/v1")
    application.include_router(admin_router, prefix="/admin", include_in_schema=False)
    application.include_router(pages_router, include_in_schema=False)

    @application.exception_handler(PublishError)
    async def _publish_error(_request: Request, exc: PublishError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=500)

    return application


app = create_app()
