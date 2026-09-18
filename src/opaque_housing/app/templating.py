"""Jinja environment for the insight app."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from opaque_housing.app.formatters import intcomma, pct
from opaque_housing.app.security import is_admin
from opaque_housing.app.urls import app_public_url, pages_url

TEMPLATE_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.filters["pct"] = pct
templates.env.filters["intcomma"] = intcomma


def render(
    request: Request,
    name: str,
    context: dict[str, Any] | None = None,
    *,
    partial: bool = False,
) -> HTMLResponse:
    payload = {
        "request": request,
        "admin": is_admin(request),
        "partial": partial,
        "app_url": app_public_url(),
        "pages_url": pages_url(),
        **(context or {}),
    }
    return templates.TemplateResponse(request, name, payload)
