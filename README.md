# Opaque housing

A public, reproducible investigation of how much residential housing is held behind opaque ownership (LLCs, corporations, trusts, shell chains), and whether that share is growing.

This is an investigation, not a product. **Milestone 1** (rules classifier, stock shares, gold labels, raw and corrected headlines), **Milestone 2** (ACRIS flow, reconstructed history, 2003–2025 window), and **Milestone 3** (LLM fallback, HPD + NY DOS, portfolio clusters, O-tiers) are in the repo. Corrected stock shares use the held-out test split only.

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
uv run oh label --sample-from data/derived/nyc/parcels_classified.parquet
uv run oh label
uv run oh eval --gold eval/gold/ci_dev.csv --split test
uv run oh eval --gold eval/gold/queue.csv --split test --with-llm
```

`oh ingest` writes immutable extracts under `data/raw/nyc/<dataset>/<date>/`. Default `all` is PLUTO + tract–NTA (`64uk-42ks`, `hm78-6dwm`). `--dataset acris` pages Master / Legals / Parties (`bnx9-e6tj`, `8h5j-fqxa`, `636b-3b5g`) for recorded years 2003–2026. `--dataset opacity` pulls HPD registrations + contacts (`tesw-yqqr`, `feu5-w2e2`) and NY DOS active corporations (`n9v6-gdp6` on data.ny.gov). `oh build` classifies residential lots. `oh flow` writes entity-buyer series. `oh opacity` writes O-tier shares, cluster links, and the top-20 entity-name review.

Raw and gold-corrected NYC stock shares are in [`docs/milestones/m1-current-stock.md`](docs/milestones/m1-current-stock.md). The gold queue stays local (`uv run oh label`).

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
- Full-city refresh size vs. GitHub-hosted runners is not yet measured (an ADR will follow if the monthly job does not fit). M2 pages a 2003–2026 ACRIS slice, not the full 46.6M-row Parties table.
- **Flow undercounts LLC membership-interest sales** (no deed) and drops $0-amount deeds from the headline series. Historical stock keeps those $0 sale deeds. See ADR 0005.
- Docker Desktop is not required for local `make test`; `docker run ... oh build --metro nyc` is a later-milestone target.
- **PLUTO has no owner mailing address** and stores condos as billing lots, not unit owners. See `docs/data_sources.md`.
- **Stock snapshots are residential lots only.** Vacant land and non-res uses are dropped in the adapter, with before/after counts.

## Working agreements

See [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) and `.cursor/rules/project.mdc`.
