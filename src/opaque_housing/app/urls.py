"""Public URLs for the insight app and the static snapshot."""

from __future__ import annotations

import os

DEFAULT_APP_URL = "https://opaque-housing-insight.fly.dev"
PAGES_URL = "https://jermhey.github.io/opaque-housing/"


def app_public_url() -> str:
    return (os.environ.get("OH_APP_PUBLIC_URL") or DEFAULT_APP_URL).rstrip("/")


def pages_url() -> str:
    return PAGES_URL
