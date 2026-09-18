"""In-memory DuckDB of allowlisted published files. I/O lives here."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import polars as pl

from opaque_housing.metrics.publish import (
    ALLOWED_FILES,
    FORBIDDEN_FILENAMES,
    GENERATED_FILES,
    PublishError,
    assert_allowed_filename,
    assert_safe_columns,
)

KNOWN_METROS = ("nyc", "phl")
LOADABLE = ALLOWED_FILES | GENERATED_FILES


def collect_keys(payload: object) -> list[str]:
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                found.add(str(key))
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


class AggregateStore:
    """DuckDB tables `{metro}_{stem}` plus JSON documents. Never registers parcels."""

    def __init__(self, published_root: Path) -> None:
        self.published_root = published_root
        self.con = duckdb.connect(":memory:")
        self.metros: list[str] = []
        self.documents: dict[str, dict[str, dict[str, Any]]] = {}
        self.tables: dict[str, set[str]] = {}
        self.reload()

    def reload(self) -> None:
        self.con.execute("DROP SCHEMA IF EXISTS aggregates CASCADE")
        self.con.execute("CREATE SCHEMA aggregates")
        self.metros = []
        self.documents = {}
        self.tables = {}
        if not self.published_root.exists():
            return
        for metro in KNOWN_METROS:
            folder = self.published_root / metro
            if not folder.is_dir():
                continue
            self._load_metro(metro, folder)
            self.metros.append(metro)

    def _load_metro(self, metro: str, folder: Path) -> None:
        self.documents[metro] = {}
        self.tables[metro] = set()
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            if path.name in FORBIDDEN_FILENAMES:
                raise PublishError(f"{path} is not a public aggregate")
            if path.name not in LOADABLE:
                continue
            assert_allowed_filename(path.name)
            if path.suffix == ".csv":
                table = pl.read_csv(path, infer_schema_length=10_000)
                assert_safe_columns(table.columns, origin=f"{metro}/{path.name}")
                ident = _table_name(metro, path.stem)
                self.con.register("_load", table)
                self.con.execute(f"CREATE TABLE aggregates.{ident} AS SELECT * FROM _load")
                self.con.unregister("_load")
                self.tables[metro].add(path.stem)
            elif path.suffix == ".json":
                raw = json.loads(path.read_text())
                if not isinstance(raw, dict):
                    raise PublishError(f"{path} is not a JSON object")
                assert_safe_columns(collect_keys(raw), origin=f"{metro}/{path.name}")
                self.documents[metro][path.stem] = raw

    def has_metro(self, metro: str) -> bool:
        return metro in self.metros

    def document(self, metro: str, stem: str) -> dict[str, Any] | None:
        return self.documents.get(metro, {}).get(stem)

    def has_table(self, metro: str, stem: str) -> bool:
        return stem in self.tables.get(metro, set())

    def frame(self, metro: str, stem: str) -> pl.DataFrame:
        if not self.has_table(metro, stem):
            return pl.DataFrame()
        ident = _table_name(metro, stem)
        result = self.con.execute(f"SELECT * FROM aggregates.{ident}").pl()
        assert_safe_columns(result.columns, origin=f"{metro}/{stem}")
        return result


def _table_name(metro: str, stem: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in f"{metro}_{stem}")
    if cleaned != f"{metro}_{stem}" or not cleaned.isidentifier():
        raise PublishError(f"unsafe table name {metro}/{stem}")
    return cleaned
