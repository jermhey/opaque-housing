"""Attach normalized names to a frame. Pure given the input frame."""

from __future__ import annotations

import polars as pl

from opaque_housing.normalize.names import normalize_name, owner_key


def attach_normalized_name(
    frame: pl.DataFrame,
    raw_col: str,
    *,
    name_col: str = "name_normalized",
    key_col: str = "owner_key",
) -> pl.DataFrame:
    if frame.is_empty() or raw_col not in frame.columns:
        return frame.with_columns(
            pl.lit("").alias(name_col),
            pl.lit("").alias(key_col),
        )
    work = frame.with_columns(pl.col(raw_col).cast(pl.Utf8).fill_null("").alias(raw_col))
    keys = work.select(raw_col).unique()
    rows: list[dict[str, str]] = []
    for rec in keys.iter_rows(named=True):
        raw = rec[raw_col]
        normalized = normalize_name(raw)
        rows.append(
            {
                raw_col: raw,
                name_col: normalized,
                key_col: owner_key(normalized) if normalized else "",
            }
        )
    return work.join(pl.DataFrame(rows), on=raw_col, how="left")
