"""Local data-layout helpers. I/O roots only; no network."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path


def data_root() -> Path:
    return Path(os.environ.get("OH_DATA_DIR", "data"))


def raw_dir(metro: str, dataset: str, retrieval_date: date | None = None) -> Path:
    day = (retrieval_date or date.today()).isoformat()
    return data_root() / "raw" / metro / dataset / day


def derived_dir(metro: str) -> Path:
    return data_root() / "derived" / metro


def published_dir(metro: str) -> Path:
    return data_root() / "published" / metro


def latest_raw_file(metro: str, dataset: str, filename: str) -> Path | None:
    root = data_root() / "raw" / metro / dataset
    if not root.exists():
        return None
    dated = sorted((path for path in root.iterdir() if path.is_dir()), reverse=True)
    for folder in dated:
        candidate = folder / filename
        if candidate.exists():
            return candidate
    return None
