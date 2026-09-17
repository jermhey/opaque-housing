"""Paged Socrata reads. Network lives here; callers write files."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import polars as pl

from opaque_housing.adapters.http import client as http_client

SOCRATA_NYC = "https://data.cityofnewyork.us"
SOCRATA_PAGE = 50_000


def iter_soda_pages(
    dataset_id: str,
    *,
    select: str,
    where: str | None = None,
    key: str = "document_id",
    page_size: int = SOCRATA_PAGE,
    host: str = SOCRATA_NYC,
    http: httpx.Client | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Keyset-paginate a SODA resource. ``key`` must be in ``select``."""
    own = http is None
    session = http or http_client(timeout=180.0)
    try:
        last: str | None = None
        while True:
            clauses: list[str] = []
            if where:
                clauses.append(f"({where})")
            if last is not None:
                escaped = last.replace("'", "''")
                clauses.append(f"{key} > '{escaped}'")
            params: dict[str, str] = {
                "$select": select,
                "$order": key,
                "$limit": str(page_size),
            }
            if clauses:
                params["$where"] = " and ".join(clauses)
            response = session.get(f"{host}/resource/{dataset_id}.json", params=params)
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not rows:
                break
            yield rows
            last_row = rows[-1]
            if not isinstance(last_row, dict) or key not in last_row:
                raise ValueError(f"SODA page missing keyset column {key}")
            last = str(last_row[key])
            if len(rows) < page_size:
                break
    finally:
        if own:
            session.close()


def write_soda_parquet(
    dest: Path,
    dataset_id: str,
    *,
    select: str,
    where: str | None = None,
    key: str = "document_id",
    page_size: int = SOCRATA_PAGE,
    host: str = SOCRATA_NYC,
    http: httpx.Client | None = None,
) -> dict[str, int]:
    """Page a SODA extract to ``dest`` as a single parquet file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    parts_dir = dest.with_name(dest.name + ".parts")
    parts_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    rows_out = 0
    try:
        for index, page in enumerate(
            iter_soda_pages(
                dataset_id,
                select=select,
                where=where,
                key=key,
                page_size=page_size,
                host=host,
                http=http,
            )
        ):
            frame = pl.DataFrame(page, infer_schema_length=0)
            part = parts_dir / f"{index:05d}.parquet"
            frame.write_parquet(part)
            parts.append(part)
            rows_out += frame.height
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
