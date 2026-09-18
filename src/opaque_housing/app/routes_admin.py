"""One-operator admin: refresh trigger and local gold labels."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from opaque_housing.app.admin_actions import (
    append_gold_label,
    gold_queue_path,
    queue_writable,
    trigger_refresh,
)
from opaque_housing.app.deps import get_store
from opaque_housing.app.security import (
    admin_configured,
    exchange_github_code,
    github_authorize_url,
    github_login_allowed,
    github_oauth_configured,
    is_admin,
    login_session,
    logout_session,
    password_ok,
)
from opaque_housing.app.store import AggregateStore
from opaque_housing.app.sync import reload_store, sync_remote
from opaque_housing.app.templating import render

router = APIRouter()


def _admin_context(**extra: object) -> dict[str, object]:
    repo, ref = sync_remote()
    return {
        "page": "admin",
        "queue_writable": queue_writable(),
        "queue_path": str(gold_queue_path()),
        "refresh_result": None,
        "sync_result": None,
        "label_result": None,
        "sync_repo": repo,
        "sync_ref": ref,
        **extra,
    }


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request) -> Response:
    if is_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return render(
        request,
        "admin/login.html",
        {
            "page": "admin",
            "configured": admin_configured(),
            "github": github_oauth_configured(),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/login")
def login_submit(request: Request, password: Annotated[str, Form()] = "") -> RedirectResponse:
    if password_ok(password):
        login_session(request)
        return RedirectResponse("/admin", status_code=303)
    return RedirectResponse("/admin/login?error=1", status_code=303)


@router.get("/logout")
def logout(request: Request) -> RedirectResponse:
    logout_session(request)
    return RedirectResponse("/", status_code=303)


@router.get("/github")
def github_start(request: Request) -> RedirectResponse:
    if not github_oauth_configured():
        raise HTTPException(status_code=404, detail="GitHub OAuth is not configured")
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    redirect = str(request.url_for("github_callback"))
    return RedirectResponse(github_authorize_url(redirect, state), status_code=303)


@router.get("/github/callback", name="github_callback")
def github_callback(
    request: Request,
    code: str = "",
    state: str = "",
) -> RedirectResponse:
    expected = request.session.get("oauth_state")
    if not code or not expected or state != expected:
        return RedirectResponse("/admin/login?error=1", status_code=303)
    redirect = str(request.url_for("github_callback"))
    login = exchange_github_code(code, redirect)
    if login is None or not github_login_allowed(login):
        return RedirectResponse("/admin/login?error=1", status_code=303)
    login_session(request)
    return RedirectResponse("/admin", status_code=303)


@router.get("", response_class=HTMLResponse)
def admin_home(
    request: Request,
    _: Annotated[None, Depends(require_admin)],
) -> HTMLResponse:
    return render(request, "admin/index.html", _admin_context())


@router.post("/refresh", response_class=HTMLResponse)
def refresh(
    request: Request,
    _: Annotated[None, Depends(require_admin)],
) -> HTMLResponse:
    result = trigger_refresh()
    return render(request, "admin/index.html", _admin_context(refresh_result=result))


@router.post("/sync", response_class=HTMLResponse)
def sync_now(
    request: Request,
    _: Annotated[None, Depends(require_admin)],
    store: Annotated[AggregateStore, Depends(get_store)],
) -> HTMLResponse:
    try:
        result: dict[str, object] = reload_store(store)
    except Exception as exc:  # noqa: BLE001 — stay on the admin page
        result = {"ok": False, "detail": str(exc)}
    return render(request, "admin/index.html", _admin_context(sync_result=result))


@router.post("/label", response_class=HTMLResponse)
def label(
    request: Request,
    _: Annotated[None, Depends(require_admin)],
    name_raw: Annotated[str, Form()] = "",
    label_value: Annotated[str, Form(alias="label")] = "",
    building_type: Annotated[str, Form()] = "",
    metro: Annotated[str, Form()] = "nyc",
) -> HTMLResponse:
    try:
        result = append_gold_label(
            name_raw=name_raw,
            label=label_value,
            building_type=building_type or None,
            metro=metro,
        )
        # Do not echo the submitted name back into HTML.
        result.pop("path", None)
        label_result: dict[str, object] = {
            "ok": True,
            "predicted": result.get("predicted"),
            "label": result.get("label"),
        }
    except Exception as exc:  # noqa: BLE001 — form errors stay on the page
        label_result = {"ok": False, "detail": str(exc)}
    return render(
        request,
        "admin/index.html",
        _admin_context(queue_path="local gold queue", label_result=label_result),
    )
