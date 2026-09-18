"""Paged ArcGIS FeatureServer reads. Network lives here."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import polars as pl

from opaque_housing.adapters.http import client as http_client

PAGE = 2_000


def next_page_size(
    got: int,
    requested: int,
    exceeded: object,
    *,
    first_page: bool,
) -> int | None:
    """Return the next ``resultRecordCount``, or ``None`` if paging is done.

    Miami-Dade MapServer/24 silently caps at 1,000 and often omits
    ``exceededTransferLimit``. A first page shorter than requested is a
    server cap, not EOF.
    """
    if got <= 0:
        return None
    if exceeded is True:
        return got if first_page and got < requested else requested
    if got == requested:
        return requested
    if first_page and got < requested:
        return got
    return None


def write_arcgis_parquet(
    dest: Path,
    query_url: str,
    *,
    out_fields: str,
    where: str = "1=1",
    page_size: int = PAGE,
    http: httpx.Client | None = None,
) -> dict[str, int]:
    """Offset-paginate a FeatureServer query to ``dest`` (no geometry)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    own = http is None
    session = http or http_client(timeout=180.0)
    parts_dir = dest.with_name(dest.name + ".parts")
    parts_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    rows_out = 0
    offset = 0
    request_size = page_size
    first_page = True
    try:
        while True:
            response = session.get(
                query_url,
                params={
                    "where": where,
                    "outFields": out_fields,
                    "returnGeometry": "false",
                    "resultOffset": str(offset),
                    "resultRecordCount": str(request_size),
                    "f": "json",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("ArcGIS query did not return an object")
            if payload.get("error"):
                raise ValueError(str(payload["error"]))
            features = payload.get("features")
            if not isinstance(features, list) or not features:
                break
            rows = [item.get("attributes") for item in features if isinstance(item, dict)]
            records = [row for row in rows if isinstance(row, dict)]
            if not records:
                break
            frame = _page_frame(records)
            part = parts_dir / f"{offset:08d}.parquet"
            frame.write_parquet(part)
            parts.append(part)
            rows_out += frame.height
            print(f"  arcgis offset={offset} rows={rows_out}", flush=True)
            nxt = next_page_size(
                len(records),
                request_size,
                payload.get("exceededTransferLimit"),
                first_page=first_page,
            )
            first_page = False
            if nxt is None:
                break
            offset += len(records)
            request_size = nxt
        if not parts:
            pl.DataFrame().write_parquet(dest)
        elif len(parts) == 1:
            parts[0].replace(dest)
        else:
            pl.scan_parquet(parts).sink_parquet(dest)
        return {"pages": len(parts), "rows": rows_out}
    finally:
        for part in parts:
            if part.exists() and part != dest:
                part.unlink()
        if parts_dir.exists():
            try:
                parts_dir.rmdir()
            except OSError:
                pass
        if own:
            session.close()


def _page_frame(page: list[dict[str, Any]]) -> pl.DataFrame:
    keys: list[str] = []
    for row in page:
        for key in row:
            if key not in keys:
                keys.append(key)
    data = {key: ["" if row.get(key) is None else str(row[key]) for row in page] for key in keys}
    return pl.DataFrame(data)
