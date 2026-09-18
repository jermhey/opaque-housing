# Opaque housing

A public, reproducible investigation of how much residential housing is held behind opaque ownership (LLCs, corporations, trusts, shell chains), and whether that share is growing.

This is an investigation, not a product. **Milestones 1–5** are in the repo: NYC stock/flow/opacity, a static site, and a Philadelphia adapter with a NYC vs PHL compare page. Cook County and Miami-Dade County adapters use the same pipeline (ADR 0012–0014). Corrected stock shares use the held-out NYC test split only.

Live investigation (Fly): [https://opaque-housing-insight.fly.dev/](https://opaque-housing-insight.fly.dev/). Static snapshot (GitHub Pages): [https://jermhey.github.io/opaque-housing/](https://jermhey.github.io/opaque-housing/). The insight app is FastAPI + DuckDB (`uv run oh serve`): mix-adjusted NYC vs PHL / Cook / Dade, definition toggles, anonymous neighborhood HHI, and `/v1` OpenAPI (ADR 0011). It syncs allowlisted `data/published` from this repo on boot and after the monthly refresh job. It is not Evidence.dev and it is not a name or address search.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
cp .env.example .env
uv sync
make test
```

CLI entry point is `oh`:

```bash
uv run oh --help
uv run oh ingest --metro nyc
uv run oh ingest --metro nyc --dataset acris
uv run oh ingest --metro nyc --dataset opacity
uv run oh build --metro nyc
uv run oh flow --metro nyc
uv run oh opacity --metro nyc
uv run oh publish --metro nyc
uv run oh ingest --metro phl
uv run oh ingest --metro phl --dataset rtt
uv run oh build --metro phl
uv run oh flow --metro phl
uv run oh publish --metro phl
uv run oh ingest --metro cook
uv run oh ingest --metro cook --dataset sales
uv run oh build --metro cook
uv run oh flow --metro cook
uv run oh publish --metro cook
uv run oh ingest --metro dade
uv run oh build --metro dade
uv run oh flow --metro dade --sdf path/to/florida_sdf.csv
uv run oh publish --metro dade
uv run oh serve
uv run oh label --sample-from data/derived/nyc/parcels_classified.parquet
uv run oh label
uv run oh eval --gold eval/gold/ci_dev.csv --split test
uv run oh eval --gold eval/gold/queue.csv --split test --with-llm
```

`oh ingest` writes immutable extracts under `data/raw/<metro>/<dataset>/<date>/`. Default NYC `all` is PLUTO + tract–NTA (`64uk-42ks`, `hm78-6dwm`). `--dataset acris` pages Master / Legals / Parties (`bnx9-e6tj`, `8h5j-fqxa`, `636b-3b5g`) for recorded years 2003–2026. `--dataset opacity` pulls HPD registrations + contacts (`tesw-yqqr`, `feu5-w2e2`) and NY DOS active corporations (`n9v6-gdp6` on data.ny.gov). Cook `all` is current-year universe / addresses / characteristics / condo (`pabr-t5kh`, `3723-97qp`, `x54s-btds`, `3r7i-mrz4`); `--dataset sales` is `wvhk-k5uv`. Dade `all` is PaGis folio points; SDF is a local DOR file. `oh build` classifies residential lots and writes anonymous neighborhood concentration. `oh flow` writes entity-buyer series (Dade SDF has no grantee). `oh opacity` is NYC-only. `oh publish` copies allowlisted citywide and NTA-or-coarser aggregates into `data/published/<metro>/` and `site/data/` (other metros under `site/data/<metro>/`). It refuses parcel files, owner keys, person names, and addresses. `oh serve` loads those published files into in-memory DuckDB and serves `/v1` plus HTMX pages. On Fly, the app also pulls the latest allowlisted files from GitHub on boot and after `refresh.yml` (`POST /internal/reload`). `oh ingest --metro phl` pulls OPA `opa_properties_public` from Carto. FastAPI is the API/UI layer specified in ADR 0011.

Reproduce stock from a raw-data volume:

```bash
docker build -t opaque-housing .
docker run --rm -v "$PWD/data:/app/data" opaque-housing build --metro nyc
docker run --rm -v "$PWD/data:/app/data" -v "$PWD/site:/app/site" opaque-housing publish --metro nyc
```

Raw and gold-corrected NYC stock shares are in [`docs/milestones/m1-current-stock.md`](docs/milestones/m1-current-stock.md). M4 site notes are in [`docs/milestones/m4-site-and-refresh.md`](docs/milestones/m4-site-and-refresh.md). The gold queue stays local (`uv run oh label`).

## Honest limits

- **LLC membership-interest sales generate no deed.** Flow metrics will undercount entity turnover.
- **Co-op buildings are corporate-owned by design.** They are never counted as opaque; they are identified by building class, not name.
- **Trusts are not entities.** Most NYC/US living trusts are probate-avoidance vehicles. They are reported as their own series.
- **Public and nonprofit owners leave the private denominator** before shares are computed.
- **Gold labels for individuals stay out of the public repo.**
- **LLM fallback is names-only** and optional. Without `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL`, `oh eval --with-llm` scores rules and records that live calls were skipped.
- **Cluster review never lists HPD person names.** Seed registered-agent names are denied. Address sharing is evidence, not a cluster edge (ADR 0008).
- **Most entity *units* have a named HPD officer** (large multifamily). Most 1–4 family *entity parcels* do not. Do not quote the citywide O1 unit share as “opaque housing is rare.”
- **No entity-level or portfolio-level public pages** until an explicit review and sign-off.
- **GitHub-hosted refresh cannot cold-pull ACRIS, NY DOS, PHL RTT, or Miami-Dade** (ADR 0009, ADR 0011, ADR 0012). `refresh.yml` may update NYC PLUTO stock, PHL OPA stock, and Cook County stock+sales monthly. NYC/PHL flow and opacity are reused until a laptop run. Miami-Dade GIS/SDF stay laptop-only.
- **Cook County and Miami-Dade are counties**, not Chicago or City of Miami. Harmonized `sfr_1_4` includes 2–4 unit buildings that are not NYC 1–4 family. Cook owner names are intermittent; Florida SDF has no buyer name.
- **The insight app never loads parcel files or owner names.** Mix-adjust, definition toggles, and neighborhood HHI are computed from published aggregates (or from laptop-side concentration files that contain no keys).
- The public URL needs GitHub Pages on this repo plus a working `gh` login to push and enable it. Until that deploy succeeds, serve `site/` locally after `oh publish`.
- **Flow undercounts LLC membership-interest sales** (no deed) and drops $0-amount deeds from the headline series. Historical stock keeps those $0 sale deeds. See ADR 0005.
- Docker Desktop is not required for local `make test`. The image entrypoint is `oh`; mount `data/` (and `site/` for publish) as shown above.
- **PLUTO has no owner mailing address** and stores condos as billing lots, not unit owners. See `docs/data_sources.md`.
- **Stock snapshots are residential lots only.** Vacant land and non-res uses are dropped in the adapter, with before/after counts.

## Working agreements

See [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) and `.cursor/rules/project.mdc`.
