# Milestone 5: Philadelphia

Date: 2026-09-17. Metros: NYC + PHL. Rules `2026-09-17.3`. OPA extract 2026-09-17.

## What was built

- `PhlOpaAdapter` and `PhlRttAdapter` (Carto `opa_properties_public`, `rtt_summary`)
- `oh ingest|build|flow|publish --metro phl`
- `geo_borough` on the canonical parcel frame so stock no longer assumes a NYC BBL (ADR 0010)
- `R020_public` matches `CITY OF PHILADELPHIA` and truncated `HOUSING AUTH`
- Compare page: NYC vs PHL with identical class definitions and per-metro caveats
- PA DOS `3urc-uaba` documented; no officer names, so no PHL O-tiers

## Verified vs assumed

| Item | Status |
|---|---|
| OPA field names | Verified live on Carto 2026-09-17 |
| Category codes / descriptions | Verified. 1/2/3/14 are the residential set |
| Unit counts | **Assumed lower bound** of official description bands (ADR 0010). OPA has no `unitsres` |
| `census_tract` as GEOID | **Rejected.** Values are 1–3 digits |
| PA DOS officer names | Verified absent on `3urc-uaba` |
| RTT sale types + consideration years | Verified. `DEED` / sheriff labels; 2000–2025 populated. Citywide flow published |
| NYC vs PHL parcel share | Verified from live OPA + published NYC stock |

## Extract and filter counts

| Stage | In | Out |
|---|---:|---:|
| OPA file | 583,772 | 583,772 |
| Residential categories (drop vacant/parking) | 583,772 | **515,116** |
| Private denominator | 515,116 | **511,336** |
| RTT sale-type rows | 1,191,554 | **1,071,179** documents |
| Named sale deeds | 1,071,179 | **1,071,097** |
| Consideration ≥ $10,000 | 1,071,097 | **716,483** |
| Join to current residential OPA | 716,483 | **592,039** |
| Recorded years 2000–2025 | — | **579,112** headline sales |

## Numbers

| Series | NYC | Philadelphia |
|---|---:|---:|
| Entity share of private lots | 15.4% raw / **13.8%** corrected | **10.4%** raw |
| Entity share of 1–4 + condo lots | 7.8% | **9.3%** |
| Entity share of private units | 39.2% raw / 38.9% corrected | 17.2% lower-bound (not a census) |
| Private residential lots | 768,516 | 511,336 |
| Entity share of arm’s-length sales | **24.2%** (2003–2025) | **17.9%** (2000–2025, incl. sheriff) |
| Entity share of 1–4 + condo sales | **16.7%** | **17.0%** |

PHL entity lots: 53,053. ZIP neighborhoods: 49. PHL 2025 entity sale share: **30.1%**.

## Design flaws logged and fixed

- CLI `metro != nyc` guards on ingest/build/publish/flow
- `stock.with_borough` / `with_year_and_borough` BBL heuristic — adapters emit `geo_borough`
- Flow coverage window is per-metro (NYC 2003–2025, PHL 2000–2025)

## Resolved (2026-09-17)

- Sheriff transfers are sales: `DEED SHERIFF` and the live alias `SHERIFF'S DEED`.
- OPA unit lower bounds stand. No second unit source.

Citywide PHL flow is published (`oh flow --metro phl`). GitHub Pages still needs a one-time repo setting (Settings → Pages → GitHub Actions).

Do not start a next metro or optional enrichment until confirmed.
