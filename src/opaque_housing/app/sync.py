"""Pull allowlisted published files from GitHub. Never fetches parcel extracts."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import httpx

from opaque_housing.app.store import KNOWN_METROS, LOADABLE, AggregateStore
from opaque_housing.metrics.publish import (
    FORBIDDEN_FILENAMES,
    PublishError,
    assert_allowed_filename,
    assert_safe_columns,
    forbidden_columns,
)

DEFAULT_REPO = "jermhey/opaque-housing"
DEFAULT_REF = "main"
GITHUB_API = "https://api.github.com"
RAW_GITHUB = "https://raw.githubusercontent.com"


def sync_remote() -> tuple[str, str]:
    repo = os.environ.get("OH_GITHUB_REPO") or os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO
    ref = os.environ.get("OH_GITHUB_REF", DEFAULT_REF)
    return repo, ref


def list_allowlisted_paths(
    repo: str,
    ref: str,
    *,
    http: httpx.Client,
) -> list[tuple[str, str]]:
    url = f"{GITHUB_API}/repos/{repo}/git/trees/{ref}"
    response = http.get(url, params={"recursive": "1"})
    response.raise_for_status()
    payload = response.json()
    tree = payload.get("tree")
    if not isinstance(tree, list):
        raise PublishError("GitHub tree response is not a list")
    found: list[tuple[str, str]] = []
    for item in tree:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        parts = path.split("/")
        if len(parts) != 4 or parts[0] != "data" or parts[1] != "published":
            continue
        metro, name = parts[2], parts[3]
        if metro not in KNOWN_METROS:
            continue
        if name in FORBIDDEN_FILENAMES:
            raise PublishError(f"{path} is not a public aggregate")
        if name not in LOADABLE:
            continue
        assert_allowed_filename(name)
        found.append((metro, name))
    return found


def sync_published(
    dest: Path,
    *,
    http: httpx.Client | None = None,
    repo: str | None = None,
    ref: str | None = None,
) -> dict[str, Any]:
    """Replace local published metros with allowlisted files from GitHub."""
    remote_repo, remote_ref = sync_remote()
    repo = repo or remote_repo
    ref = ref or remote_ref
    own = http is None
    session = http or httpx.Client(timeout=60.0, follow_redirects=True)
    staging = dest.parent / f".published-sync-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    written: list[str] = []
    try:
        paths = list_allowlisted_paths(repo, ref, http=session)
        if not paths:
            raise PublishError(f"no allowlisted published files at {repo}@{ref}")
        for metro, name in paths:
            url = f"{RAW_GITHUB}/{repo}/{ref}/data/published/{metro}/{name}"
            response = session.get(url)
            response.raise_for_status()
            folder = staging / metro
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / name
            target.write_bytes(response.content)
            _assert_file_safe(target, origin=f"{metro}/{name}")
            written.append(f"{metro}/{name}")
        dest.mkdir(parents=True, exist_ok=True)
        for metro in KNOWN_METROS:
            incoming = staging / metro
            if not incoming.exists():
                continue
            current = dest / metro
            if current.exists():
                shutil.rmtree(current)
            shutil.move(str(incoming), str(current))
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if own:
            session.close()
    return {
        "ok": True,
        "repo": repo,
        "ref": ref,
        "files": sorted(written),
        "count": len(written),
    }


def reload_store(store: AggregateStore) -> dict[str, Any]:
    report = sync_published(store.published_root)
    store.reload()
    return report


def _assert_file_safe(path: Path, *, origin: str) -> None:
    if path.suffix == ".csv":
        header = path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        names = header[0].split(",") if header else []
        leaked = forbidden_columns([item.strip() for item in names])
        if leaked:
            raise PublishError(f"{origin} has unpublished columns: {', '.join(leaked)}")
        assert_safe_columns([item.strip() for item in names], origin=origin)
    elif path.suffix == ".json":
        text = path.read_text(encoding="utf-8")
        if '"owner_key"' in text or '"owner_name"' in text:
            raise PublishError(f"{origin} looks like it contains unpublished keys")
