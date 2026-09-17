# ADR 0009: Static site and GitHub-hosted refresh limits

Status: accepted (2026-09-17)

## Context

Milestone 4 needs a public site (brief §9) and a scheduled refresh. ADR 0001 deferred Evidence.dev to M4 and said a switch of site generator needs a new ADR. GitHub-hosted runners cannot cold-pull ACRIS Parties (25.5M rows in the 2003–2026 window) or a 4.3M-row NY DOS extract in a monthly job. Measured sizes that *do* fit a runner: PLUTO `$select` ~67 MB; HPD regs + contacts ~105 MB; tract–NTA ~0.2 MB.

## Decision

### Site generator

The public site is **static HTML + CSS + JS** under `site/`, reading committed JSON/CSV aggregates. It is not an Evidence.dev or Observable Framework app.

Why: the metrics are already computed by `oh build` / `oh flow` / `oh opacity`. Evidence’s value is SQL-over-warehouse; we are not publishing a warehouse. A Node site generator would add a toolchain without changing the numbers. Switching later to Evidence still requires only a new ADR and a reader of the same published files.

### What is published

`oh publish` copies an **allowlist** of citywide and NTA-or-coarser aggregates into `data/published/<metro>/` and `site/data/`. Parcel files, owner keys, HPD person names, addresses, and cluster member lists are not copied. NTA cells with fewer than 10 residential units keep `suppressed=true` and null shares (already in `stock_by_nta_type`).

### Refresh on GitHub-hosted runners

`refresh.yml` may ingest PLUTO and tract–NTA, then run `oh build` and `oh publish`. It does **not** cold-pull ACRIS, HPD, or NY DOS. Flow, history, and opacity series are reused from the last published full run until a self-hosted (or laptop) refresh writes new files.

A row-count gate fails the job if PLUTO residential lots change by more than 20% vs the last published stock run.

### Hosting

GitHub Pages from `site/`, via `deploy.yml`. Intended URL after the first successful deploy: `https://jermhey.github.io/opaque-housing/`.

## Consequences

Monthly Actions will update current-stock headlines when PLUTO moves, and will leave 2003–2025 flow and O-tiers stale until someone runs the full local pipeline. That staleness is shown on the freshness page. Entity-level pages remain unpublished (brief §10).
