# ADR 0010: Philadelphia stock definitions

Status: accepted (2026-09-17)

## Context

Milestone 5 adds a Philadelphia adapter. Live `opa_properties_public` (Carto, 2026-09-17) has owner names and a use category, but no PLUTO-style `unitsres`. `census_tract` values are 1–3 digits, not 2020 GEOIDs. `R020_public` only named New York agencies, so `CITY OF PHILADELPHIA` and truncated `PHILADELPHIA HOUSING AUTH` would stay in the private denominator.

`stock.with_borough` derived borough from the first digit of a NYC BBL. That is a downstream NYC assumption (a design flaw under the brief).

## Decision

### Residential filter

Keep OPA `category_code` in `{1,2,3,14}` (Single Family, Multi Family, Mixed Use, Apartments > 4 Units). Drop rows whose `building_code_description` contains `VACANT LAND` or `CONDO PARKING`. Other categories (vacant, garage, commercial, industrial, hotel, office, special, retail) stay out, with before/after counts.

### Units

OPA has no unit census. Unit-weighted shares use the **lower bound of the official building-code description band** when one exists:

| Official description | `building_type` | `res_units` |
|---|---|---|
| `RES CONDO` | `condo_unit` | 1 |
| `SINGLE FAMILY` (category 1, not condo) | `sfr_1_4` | 1 |
| `APT 2-4 UNITS` | `sfr_1_4` | 2 |
| `APTS 5-50 UNITS` | `small_mf` | 5 |
| `APTS 51-100 UNITS` | `large_mf` | 51 |
| `APTS 100+ UNITS` | `large_mf` | 100 |
| category 14 without a band | `small_mf` | 5 |
| other category 2 | `sfr_1_4` | 2 |
| category 3 Mixed Use | `mixed_use_res` | 1 |

Parcel-weighted shares are the comparable NYC vs PHL headline. Unit-weighted PHL figures are a lower bound, not a dwelling census. Confirmed 2026-09-17: do **not** wait for another unit source.

### Geography

`geo_borough` is `Philadelphia`. `geo_neighborhood` is OPA `zip_code` (5-digit). `geo_tract` is left null — the 1–3 digit `census_tract` field is not a 2020 GEOID and is not padded into one.

Adapters emit `geo_borough`. `stock.with_borough` uses that column when present and only falls back to the NYC BBL heuristic for older frames.

### Owner name

Classify `owner_1` only. `owner_2` is a second recorded owner (often a spouse) and is not concatenated.

### Public names

`R020` also matches `CITY OF PHILADELPHIA` and `HOUSING AUTH` (OPA truncates `AUTHORITY`). LLCs stay out of public.

### Opacity / PA DOS

`data.pa.gov` `3urc-uaba` is a 2.36M-row current business list with **no officer names**. O-tiers are not computed for PHL in this milestone.

### Flow

Confirmed 2026-09-17: sale deeds are `DEED`, `DEED SHERIFF`, and `SHERIFF'S DEED` (both sheriff labels appear in live `rtt_summary`). Other deed-like types (`DEED MISCELLANEOUS`, land-bank, condemnation) stay out. Consideration `>= 10000` and recording years **2000–2025** are the PHL coverage window (`oh flow --metro phl`).

## Consequences

NYC vs PHL must lead with parcel shares. PHL ZIP “neighborhoods” are not NTAs. Gold correction is NYC-only.
