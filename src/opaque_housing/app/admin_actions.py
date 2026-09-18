"""Admin-only disk and GitHub Actions helpers. No public names are read back."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import polars as pl

from opaque_housing.classify.pipeline import classify_owner
from opaque_housing.schema import BuildingType, OwnerClass

DEFAULT_QUEUE = Path("eval/gold/queue.csv")
DEFAULT_REPO = "jermhey/opaque-housing"


def gold_queue_path() -> Path:
    raw = os.environ.get("OH_GOLD_QUEUE")
    return Path(raw) if raw else DEFAULT_QUEUE


def queue_writable() -> bool:
    path = gold_queue_path()
    parent = path.parent
    if path.exists():
        return os.access(path, os.W_OK)
    return parent.exists() and os.access(parent, os.W_OK)


def append_gold_label(
    *,
    name_raw: str,
    label: str,
    building_type: str | None = None,
    metro: str = "nyc",
) -> dict[str, Any]:
    """Write one labeled row. Does not return other queue names."""
    if not name_raw.strip():
        raise ValueError("name_raw is required")
    OwnerClass(label)
    parsed_type = BuildingType(building_type) if building_type else None
    predicted = classify_owner(name_raw, parsed_type).owner_class.value
    path = gold_queue_path()
    if not queue_writable():
        raise OSError("gold queue is not writable on this host; run `oh label` on the laptop")
    row = {
        "metro_id": metro,
        "name_raw": name_raw.strip(),
        "building_type": building_type or "",
        "owner_class": predicted,
        "label": label,
        "labeled_at": datetime.now(tz=UTC).isoformat(),
        "split": "train",
    }
    if path.exists():
        table = pl.read_csv(path, infer_schema_length=0)
        table = pl.concat([table, pl.DataFrame([row])], how="diagonal_relaxed")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        table = pl.DataFrame([row])
    table.write_csv(path)
    return {"wrote": True, "path": str(path), "predicted": predicted, "label": label}


def trigger_refresh() -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO)
    if not token:
        return {
            "ok": False,
            "mode": "laptop",
            "command": "gh workflow run refresh.yml",
            "detail": "No GITHUB_TOKEN on this process. Dispatch from the laptop or set the token.",
        }
    url = f"https://api.github.com/repos/{repo}/actions/workflows/refresh.yml/dispatches"
    response = httpx.post(
        url,
        json={"ref": os.environ.get("GITHUB_REF_NAME", "main")},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=20.0,
    )
    if response.status_code not in {201, 204}:
        return {
            "ok": False,
            "mode": "github",
            "status": response.status_code,
            "detail": response.text[:300],
        }
    return {"ok": True, "mode": "github", "repo": repo, "workflow": "refresh.yml"}
