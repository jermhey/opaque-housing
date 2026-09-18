"""Carto SQL extracts. Network lives here; callers write files."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from opaque_housing.adapters.http import stream_to_path
from opaque_housing.adapters.phl.sources import CartoSpec


def carto_csv_url(spec: CartoSpec) -> str:
    query = urlencode({"q": spec.query, "format": "csv"})
    return f"{spec.host}/api/v2/sql?{query}"


def write_carto_csv(dest: Path, spec: CartoSpec, timeout: float | None = None) -> None:
    stream_to_path(carto_csv_url(spec), dest, timeout=timeout or spec.timeout)
