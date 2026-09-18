"""Admin session helpers. One operator; no public accounts."""

from __future__ import annotations

import os
import secrets
from urllib.parse import urlencode

import httpx
from starlette.requests import Request

GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_USER = "https://api.github.com/user"


def session_secret() -> str:
    return (
        os.environ.get("ADMIN_SECRET") or os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
    )


def admin_configured() -> bool:
    return bool(os.environ.get("ADMIN_SECRET")) or bool(
        os.environ.get("GITHUB_OAUTH_CLIENT_ID") and os.environ.get("ADMIN_GITHUB_LOGIN")
    )


def github_oauth_configured() -> bool:
    return bool(
        os.environ.get("GITHUB_OAUTH_CLIENT_ID")
        and os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")
        and os.environ.get("ADMIN_GITHUB_LOGIN")
    )


def is_admin(request: Request) -> bool:
    return bool(request.session.get("admin"))


def login_session(request: Request) -> None:
    request.session["admin"] = True


def logout_session(request: Request) -> None:
    request.session.clear()


def password_ok(password: str) -> bool:
    expected = os.environ.get("ADMIN_SECRET")
    if not expected:
        return False
    return secrets.compare_digest(password, expected)


def github_authorize_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id": os.environ["GITHUB_OAUTH_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "scope": "read:user",
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE}?{urlencode(params)}"


def github_login_allowed(login: str) -> bool:
    allowed = os.environ.get("ADMIN_GITHUB_LOGIN", "")
    return bool(allowed) and secrets.compare_digest(login, allowed)


def exchange_github_code(code: str, redirect_uri: str) -> str | None:
    token_resp = httpx.post(
        GITHUB_TOKEN,
        data={
            "client_id": os.environ["GITHUB_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["GITHUB_OAUTH_CLIENT_SECRET"],
            "code": code,
            "redirect_uri": redirect_uri,
        },
        headers={"Accept": "application/json"},
        timeout=20.0,
    )
    token_resp.raise_for_status()
    payload = token_resp.json()
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        return None
    user_resp = httpx.get(
        GITHUB_USER,
        headers={"Authorization": f"Bearer {access}", "Accept": "application/json"},
        timeout=20.0,
    )
    user_resp.raise_for_status()
    login = user_resp.json().get("login")
    if not isinstance(login, str):
        return None
    return login
