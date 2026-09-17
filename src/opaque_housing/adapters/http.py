"""Shared HTTP client for adapters. Identifies the project on every request."""

import os

import httpx

DEFAULT_USER_AGENT = "opaque-housing/0.1 (residential-ownership-research)"


def user_agent() -> str:
    return os.environ.get("OH_USER_AGENT", DEFAULT_USER_AGENT)


def client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": user_agent()},
        timeout=60.0,
        follow_redirects=True,
    )
