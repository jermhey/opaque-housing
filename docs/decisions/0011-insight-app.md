# ADR 0011: Insight app over published aggregates

Status: accepted (2026-09-17)

## Context

ADR 0009 made the public surface static HTML on GitHub Pages, reading committed `oh publish` files. That snapshot cannot decompose NYC vs Philadelphia, apply definition toggles live, or show neighborhood concentration without shipping a second copy of the numbers in JavaScript.

Brief §10 and the product choice: this stays an investigation of **aggregates**. Public name, address, BBL, or OPA-account search is out. Entity and portfolio pages stay unpublished. The pipeline (`oh ingest|build|flow|publish`) remains the source of truth.

## Decision

### Public surface

A FastAPI app in this repo is a second public surface. It reads **only** allowlisted `oh publish` outputs (the same `ALLOWED_FILES` / `FORBIDDEN_COLUMNS` / `FORBIDDEN_FILENAMES` as publish). It never loads `parcels_classified.parquet`, owner names, `owner_key`, HPD people, or cluster member lists on the public host.

The `site/` tree remains a static snapshot until an app host is up. Pages may keep downloads; they do not become a lookup UI.

UI is FastAPI templates + HTMX + the existing `site/assets` visual language. A second JS framework still needs its own ADR (`site/README.md`).

### What the app computes

These are metrics on published or publishable aggregates, not live reclassification:

1. **Mix-adjusted NYC vs PHL** from `stock_by_building_type.csv` in both metros. Philadelphia standardized to NYC’s building-type mix (and the reverse) answers whether NYC’s higher entity *lot* share is composition or a higher entity rate inside the same types.
2. **Definition playground** from precomputed cubes (`headlines.json` / `stock_sensitivity.csv`, `flow_sensitivity.csv`). Toggles: parcel vs unit weight; entity-only vs entity+trust; flow $10k / $0 / $100k; PHL with vs without sheriff deeds. The server does not reclassify millions of rows.
3. **Anonymous neighborhood concentration.** From classified parcels *on the laptop*, `oh build` writes `concentration_by_neighborhood.csv`: HHI of `owner_key` and the share of units (and lots) held by the largest 5 / 10 / 20 name-keys. No keys, names, or addresses. Cells under 10 units are suppressed.

Citywide “top portfolio” lists are **not** published. Cluster 1 on the opacity graph is a known likely false merge (officer-name chain; see `docs/milestones/m3-llm-and-opacity.md`). Neighborhood HHI does not rank or name anyone.

### What stays out

- Public search of address, BBL, OPA account, or owner name
- Entity or portfolio pages
- Serving parcel files or cluster member lists
- Live LLM, ACRIS, or NY DOS pulls on the public host

### Admin

`/admin` is one operator (shared secret and/or GitHub OAuth). Actions: trigger the existing `refresh.yml` `workflow_dispatch`; show last-run honesty; a label form that writes the local gold queue only if the process has disk. Gold individual names are not stored on the public VM.

### Refresh (amends ADR 0009)

`refresh.yml` may rebuild **NYC PLUTO stock and PHL OPA stock** on the monthly (or dispatched) job. Both fit a runner. PHL RTT (~206 MB), ACRIS, HPD, and NY DOS stay laptop-only. Freshness UI must say which series are stale.

### Host

A small VM (Fly.io / Render) can serve the app. GitHub Actions still builds aggregates. No warehouse. DuckDB in the app process holds only published tables (memory or `data/app.duckdb` with the same allowlist).

The image may ship a fallback copy of `data/published`. The live host **syncs allowlisted files from GitHub** on boot and after `refresh.yml` pushes (`POST /internal/reload` with `OH_SYNC_TOKEN`). It never fetches parcel files.

## Consequences

Static Pages is no longer the only public surface. Leak tests apply to the API the same way they apply to `oh publish`. Mix-adjust and anonymous HHI are in-scope; public lookup is not.
