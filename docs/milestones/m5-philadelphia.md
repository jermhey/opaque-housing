# Milestone 5: Philadelphia

Date: 2026-09-17. Metros: NYC + PHL. Rules `2026-09-17.3`. OPA extract 2026-09-17.

## What was built

- `PhlOpaAdapter` and `PhlRttAdapter` (Carto `opa_properties_public`, `rtt_summary`)
- `oh ingest|build|publish --metro phl`
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
| RTT `DEED` + consideration years | Verified. 2000–2025 populated. Citywide PHL flow not published |
| NYC vs PHL parcel share | Verified from live OPA + published NYC stock |

## Extract and filter counts

| Stage | In | Out |
|---|---:|---:|
| OPA file | 583,772 | 583,772 |
| Residential categories (drop vacant/parking) | 583,772 | **515,116** |
| Private denominator | 515,116 | **511,336** |

## Numbers

| Series | NYC | Philadelphia |
|---|---:|---:|
| Entity share of private lots | 15.4% raw / **13.8%** corrected | **10.4%** raw |
| Entity share of 1–4 + condo lots | 7.8% | **9.3%** |
| Entity share of private units | 39.2% raw / 38.9% corrected | 17.2% lower-bound (not a census) |
| Private residential lots | 768,516 | 511,336 |

PHL entity lots: 53,053. ZIP neighborhoods: 49.

## Design flaws logged and fixed

- CLI `metro != nyc` guards on ingest/build/publish
- `stock.with_borough` BBL heuristic — adapters now emit `geo_borough`

## Open questions

- Treat `DEED SHERIFF` as a sale? Not in the headline set.
- A real PHL unit census would need another source.
- Citywide PHL flow series (RTT is wired; not published).
- GitHub Pages enablement still needs a repo setting or a workflow with `enablement: true` after this push.

Do not start a next metro or optional enrichment until confirmed.
