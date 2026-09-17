# Opaque housing

A public, reproducible investigation of how much residential housing is held behind opaque ownership (LLCs, corporations, trusts, shell chains), and whether that share is growing.

This is an investigation, not a product. **Milestone 0** (scaffold, NYC source verification, PLUTO fixture adapter) is in the repo. Headline ownership shares are not computed yet.

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
```

## Honest limits

- **LLC membership-interest sales generate no deed.** Flow metrics will undercount entity turnover.
- **Co-op buildings are corporate-owned by design.** They are never counted as opaque; they are identified by building class, not name.
- **Trusts are not entities.** Most NYC/US living trusts are probate-avoidance vehicles. They are reported as their own series.
- **Public and nonprofit owners leave the private denominator** before shares are computed.
- **Gold labels for individuals stay out of the public repo.**
- **No entity-level or portfolio-level public pages** until an explicit review and sign-off.
- Full-city refresh size vs. GitHub-hosted runners is not yet measured (an ADR will follow if the monthly job does not fit). ACRIS Parties alone is 46.6M rows.
- Docker Desktop is not required for local `make test`; `docker run ... oh build --metro nyc` is a later-milestone target.
- **PLUTO has no owner mailing address** and stores condos as billing lots, not unit owners. See `docs/data_sources.md`.
- **Stock snapshots are residential lots only.** Vacant land and non-res uses are dropped in the adapter, with before/after counts.

## Working agreements

See [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) and `.cursor/rules/project.mdc`.
