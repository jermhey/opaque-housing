# ADR 0001: M0 stack pins

Status: accepted (2026-09-16)

## Decision

- Python 3.12, managed by `uv`
- `ruff` + `pyright` + `pytest`
- DuckDB + Polars + Pydantic (canonical row models)
- Typer CLI (`oh`)
- Makefile (not justfile)
- Evidence.dev deferred to M4; `site/` is a placeholder
- HTTP via `httpx` with a project User-Agent

## Why

These are the brief defaults. Pydantic is used instead of Pandera in M0 because the canonical schema is a set of row records, not DataFrame contracts. Evidence is unused until publish, so a full Node app is not scaffolded yet.

## Consequences

Adding a DataFrame-level validator (Pandera) later is allowed if we need it. Switching the site generator requires a new ADR.
