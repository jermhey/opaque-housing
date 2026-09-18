# ADR 0013: Cook County stock and flow

Status: accepted (2026-09-18)

## Context

Cook County Assessor open data (live 2026-09-18) has a current-year parcel universe, a current-year owner-name join, improvement unit counts, condo parking/common-area flags, and a multi-decade sales file. Geography is the **county**, not the City triad.

Verified IDs and fields (catalog + `$select` samples; do not invent others):

- Universe `pabr-t5kh`: `pin`, `class`, `triad_name`, `township_name`, `nbhd_code`, `zip_code`, `cook_municipality_name`, `census_tract_geoid`, `year` (tax year **2026** only, 1,863,562 rows), `row_id`
- Addresses `3723-97qp`: `pin`, `year`, `owner_address_name`, `mail_address_name`, `owner_address_full`. Official caveat: owner strings are intermittent. Ingest **`year=2026` only** (the historic file is tens of millions of rows).
- Characteristics `x54s-btds`: `pin`, `year`, `class`, `char_apts` (live 2026 class 211 values: `Two` / `Three` / `Four` / `Five` / `Six` / `None`)
- Condo characteristics `3r7i-mrz4`: `pin`, `year`, `is_parking_space`, `is_common_area`
- Sales `wvhk-k5uv`: `pin`, `doc_no`, `sale_date`, `sale_price`, `deed_type`, `mydec_deed_type`, `buyer_name`, `seller_name`, `is_multisale`, `sale_filter_deed_type`, `sale_filter_less_than_10k`, `year`, `row_id`

Class meanings from the official CCAO `class_dict` (reporting `class_code`).

## Decision

### Residential filter

Keep official residential / multi-family classes used as dwellings:

- 1-family: `202`–`210`, `234`, `278`, `295`
- 2–6 unit: `211`; mixed-use 2–6: `212`
- Cooperative: `213`
- Condo: `299` (drop when `is_parking_space` or `is_common_area` is true)
- 7+ rental: `313`, `314`, `315`, `318`, `391`, `396`; rental condo `399`
- Other occupied residential: `218`, `219` (B&B), `225` (SRO)

Drop vacant/exempt/commercial land and garages (`EX`, `RR`, `100`, `190`, `200`, `201`, `224`, `236`, `239`–`241`, `288`, `290`, `297`, `300`, `301`, `390`, and class 4+). Log `cook_residential_only`.

### Units and types

| Class | `building_type` | `res_units` |
|---|---|---|
| 202–210, 234, 278, 295 | `sfr_1_4` | 1 |
| 211 | `sfr_1_4` if `char_apts` in 2–4; `small_mf` if 5–6; else `sfr_1_4` with 2 | parsed word count |
| 212 | `mixed_use_res` | `char_apts` or 2 |
| 213 | `coop_building` | 1 |
| 218, 219, 225 | `other_res` | 1 |
| 299, 399 | `condo_unit` | 1 |
| 313–318, 391, 396 | `small_mf` if units < 20 else `large_mf` | 7 if unknown |

`char_apts` is a word (`Two`), not a digit.

### Geography

`geo_borough` = `township_name`. `geo_neighborhood` = `{township_name} {nbhd_code}`. `geo_tract` = `census_tract_geoid` when it looks like a 11-digit GEOID. Do **not** use Chicago community areas (city-only).

### Owner name

Classify `owner_address_name` for the matching tax year. Fall back to `mail_address_name` only when owner is blank. `TAXPAYER OF` / `CURRENT OWNER` are `unknown` (`R021`), not LLCs. `CHICAGO TITLE LAND TRUST` stays `trust` (`R060`). Public: `CITY OF CHICAGO`, `COOK COUNTY`, `HOUSING AUTH` (existing).

### Flow

Sale deed when official `sale_filter_deed_type` is false (live: Warranty / Trustee / other still in the file; the flag is the Assessor’s non-sale cut). Grantee = `buyer_name`. Consideration = `sale_price`. Coverage window **2000–2025** (usable volume starts in 2000; 2026 is a partial year). Same $10k named-grantee headline as NYC/PHL. Sensitivity adds `exclude_quit_claim` (`deed_type` / `mydec` quit claim).

## Consequences

`sfr_1_4` includes Cook 211 2–4 flats; that is not NYC 1–4 family. Owner names are spotty. Land trusts hide beneficial owners. Timed 2026-09-18; stock+sales are on the monthly runner.
