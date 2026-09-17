"""Shared HTTP client for adapters. Identifies the project on every request."""

import os
from pathlib import Path

import httpx

DEFAULT_USER_AGENT = "opaque-housing/0.1 (residential-ownership-research)"


def user_agent() -> str:
    return os.environ.get("OH_USER_AGENT", DEFAULT_USER_AGENT)


def client(timeout: float = 60.0) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": user_agent()},
        timeout=timeout,
        follow_redirects=True,
    )


def stream_to_path(url: str, dest: Path, timeout: float = 300.0) -> None:
    """Download ``url`` to ``dest`` via a temp file so a failed pull is not kept."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    with client(timeout=timeout) as http:
        with http.stream("GET", url) as response:
            response.raise_for_status()
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
    tmp.replace(dest)
