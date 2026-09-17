# Opaque housing

A public, reproducible investigation of how much residential housing is held behind opaque ownership (LLCs, corporations, trusts, shell chains), and whether that share is growing.

This is an investigation, not a product. **Milestone 1** (rules classifier, stock shares, gold labels, raw and corrected headlines) and **Milestone 2** (ACRIS flow, reconstructed history, 2003–2025 window) are in the repo. Corrected stock shares use the held-out test split only.

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
uv run oh build --metro nyc
uv run oh flow --metro nyc
uv run oh label --sample-from data/derived/nyc/parcels_classified.parquet
uv run oh label
uv run oh eval --gold eval/gold/ci_dev.csv --split test
```

`oh ingest` writes immutable extracts under `data/raw/nyc/<dataset>/<date>/`. Default `all` is PLUTO + tract–NTA (`64uk-42ks`, `hm78-6dwm`). `--dataset acris` pages Master / Legals / Parties (`bnx9-e6tj`, `8h5j-fqxa`, `636b-3b5g`) for recorded years 2003–2026. `oh build` classifies residential lots. `oh flow` writes entity-buyer series, a sensitivity table, reconstructed year-end stock, and a PLUTO consistency check.

Raw and gold-corrected NYC stock shares are in [`docs/milestones/m1-current-stock.md`](docs/milestones/m1-current-stock.md). The gold queue stays local (`uv run oh label`).

## Honest limits

- **LLC membership-interest sales generate no deed.** Flow metrics will undercount entity turnover.
- **Co-op buildings are corporate-owned by design.** They are never counted as opaque; they are identified by building class, not name.
- **Trusts are not entities.** Most NYC/US living trusts are probate-avoidance vehicles. They are reported as their own series.
- **Public and nonprofit owners leave the private denominator** before shares are computed.
- **Gold labels for individuals stay out of the public repo.**
- **No entity-level or portfolio-level public pages** until an explicit review and sign-off.
- Full-city refresh size vs. GitHub-hosted runners is not yet measured (an ADR will follow if the monthly job does not fit). M2 pages a 2003–2026 ACRIS slice, not the full 46.6M-row Parties table.
- **Flow undercounts LLC membership-interest sales** (no deed) and drops $0-amount deeds from the headline series. Historical stock keeps those $0 sale deeds. See ADR 0005.
- Docker Desktop is not required for local `make test`; `docker run ... oh build --metro nyc` is a later-milestone target.
- **PLUTO has no owner mailing address** and stores condos as billing lots, not unit owners. See `docs/data_sources.md`.
- **Stock snapshots are residential lots only.** Vacant land and non-res uses are dropped in the adapter, with before/after counts.

## Working agreements

See [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) and `.cursor/rules/project.mdc`.
