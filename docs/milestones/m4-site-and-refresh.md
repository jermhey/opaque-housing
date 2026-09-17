# Milestone 4: Site and refresh

Date: 2026-09-17. Metro: NYC. Site generator: static HTML (ADR 0009). Rules `2026-09-16.2`. Opacity `2026-09-17.1`.

## What was built

- ADR 0009: static site instead of Evidence.dev; GitHub Pages; GitHub-hosted refresh updates PLUTO + tract–NTA stock only
- `oh publish`: allowlisted citywide and NTA-or-coarser aggregates → `data/published/nyc/` and `site/data/`
- Neighborhood rollup with NTA names; cells under 10 units stay suppressed
- Correction rates are reused when gold labels are not on the runner
- Quality gate: fail if private parcel count moves more than 20% vs last publish
- Section 9 pages: findings, neighborhoods (borough cards + table), trends, building types, methodology, dictionary, limitations, freshness, downloads
- `refresh.yml` (monthly + manual) and `deploy.yml` (GitHub Pages from `site/`)
- Docker volume recipe in the README (`oh build` / `oh publish`)

## Verified vs assumed

| Item | Status |
|---|---|
| Publishable vs leaky derived files | Verified. Parcel parquets, `opacity_results.json`, `owner_links.csv`, `denied_addresses.csv`, and the LLM cache are refused |
| NTA names from `hm78-6dwm` | Verified. `ntacode` / `ntaname` / `boroname` |
| Site numbers vs M1–M3 headlines | Verified in the browser against `site.json` |
| `make test` | Verified. 102 passed |
| GitHub Pages public URL | **Not deployed.** `gh` for `jermhey` has an invalid keyring token |
| Unattended `refresh.yml` | **Not run.** Same auth block; workflow is in the repo |
| `docker run … oh build` | **Not run.** Docker was not available in this environment |
| Optional OpenSanctions / ICIJ flags | Not started (optional) |

## Published files

Allowlist only. `site.json` is 170 KB. `stock_by_nta_type.csv` is the largest CSV (470 KB). No owner keys, person names, or addresses.

## Numbers on the site (same extracts as M1–M3)

| Series | Figure |
|---|---|
| Entity share of private units | **38.9%** corrected (raw 39.2%; 37.0–41.0; n=305) |
| Entity share of private lots | **13.8%** corrected (raw 15.4%) |
| 1–4 family + condo units | **9.8%** corrected (raw 11.5%) |
| Entity buyers 2003–2025 | **24.2%** of sales; **59.6%** of units |
| Entity-unit O1 / O3 | **92.0%** / **7.0%** |
| Borough entity unit share | Bronx 47.7%; Manhattan 45.6%; Brooklyn 42.4%; Queens 29.1%; Staten Island 11.6% |

204 NTAs. 201 shown by default (3 suppressed). Example: Greenpoint (BK0101) 57.5% entity units.

## Open questions (carried)

- Public URL and first unattended refresh need `gh auth refresh -h github.com`, a push, and Pages enabled
- Staten Island `RPTT` as a sale; live PAD; gold matrix on buyer names
- Cluster 1 person-name collisions; `HOUSING DEV FUND` miss
- Live LLM eval when `ANTHROPIC_API_KEY` exists

## What this milestone is not

- No public URL until you re-auth and push
- No Philadelphia adapter (M5)
- No entity or portfolio pages
- No sanctions/leaks enrichment

Do not start M5 until confirmed.
