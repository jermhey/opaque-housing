# ADR 0014: Miami-Dade County stock and flow

Status: accepted (2026-09-18)

## Context

Miami-Dade property appraisal is county-wide. Live GIS (2026-09-18) **Property @ PaGis** `MD_LandInformation/MapServer/24` has 943,689 folio **points** (polygons undercount stacked condos).

Verified fields: `FOLIO`, `TRUE_OWNER1`, `TRUE_OWNER2`, `DOR_CODE_CUR`, `DOR_DESC`, `UNIT_COUNT`, `CONDO_FLAG`, `PARENT_FOLIO`, `TRUE_SITE_CITY`, `TRUE_SITE_ZIP_CODE`, `TRUE_MAILING_ADDR1`, `ASSESSMENT_YEAR_CUR`, `CANCEL_FLAG`. There is no municipality polygon field and no `NBRHD_CD` on this layer.

Four-digit `DOR_CODE_CUR` values seen live, with official `DOR_DESC`:

- `0101` RESIDENTIAL - SINGLE FAMILY : 1 UNIT
- `0407` RESIDENTIAL - TOTAL VALUE : CONDOMINIUM - RESIDENTIAL (`CONDO_FLAG=Y`)
- `0410` RESIDENTIAL - TOTAL VALUE : TOWNHOUSE
- `0802` / `0803` MULTIFAMILY 2-9 UNITS
- `0303` MULTIFAMILY 10 UNITS PLUS
- `0508` COOPERATIVE - RESIDENTIAL
- `0081` / `0000` vacant or reference folio — drop

Florida DOR **SDF** (2024/2025 user’s guide, Section 2) is the free sales file. Production CSVs have **no header**. Fields include `CO_NO` (Miami-Dade = **23**), `PARCEL_ID`, `QUAL_CD`, `SALE_YR`, `SALE_MO`, `SALE_PRC`, `CLERK_NO`, `OR_BOOK`, `OR_PAGE`, `SALE_ID_CD`. **There is no grantee / buyer name field.**

## Decision

### Residential filter

Keep rows where `CANCEL_FLAG` is not `Y` and `DOR_DESC` (uppercase) matches a dwelling use:

- `RESIDENTIAL - SINGLE FAMILY`
- `CONDOMINIUM - RESIDENTIAL`
- `TOWNHOUSE` and not `VACANT`
- `MULTIFAMILY 2-9 UNITS`
- `MULTIFAMILY 10 UNITS PLUS`
- `COOPERATIVE - RESIDENTIAL`

Drop vacant, reference folio, parking, common area, dock-only, hotel, commercial, and government vacant. Log `dade_residential_only`. Blank `TRUE_OWNER1` (s. 119.071 redaction) stays in the file as `unknown`; do not drop.

### Units and types

Use `DOR_DESC` first, then `UNIT_COUNT`:

| Signal | `building_type` | `res_units` |
|---|---|---|
| condominium - residential | `condo_unit` | 1 |
| cooperative - residential | `coop_building` | `UNIT_COUNT` or 1 |
| single family or townhouse | `sfr_1_4` | `UNIT_COUNT` or 1 |
| multifamily 2–9, units 2–4 | `sfr_1_4` | units |
| multifamily 2–9, units 5–9 or unknown | `small_mf` | units or 5 |
| multifamily 10+, units < 20 | `small_mf` | units or 10 |
| multifamily 10+, units ≥ 20 | `large_mf` | units |

Classify `TRUE_OWNER1` only (PHL `owner_1` rule).

### Geography

`geo_borough` = `TRUE_SITE_CITY`. `geo_neighborhood` = first five characters of `TRUE_SITE_ZIP_CODE`. `geo_tract` is null. Charts say Miami-Dade County, not Miami.

### Flow

`oh ingest --metro dade --dataset sdf` reads a local DOR SDF (headerless positional names, or a headered copy). `CO_NO` must be `23`. `QUAL_CD` in `{01, 1}` is `sale_deed`; other qualification codes are `other`. Consideration = `SALE_PRC`. Date = first of `SALE_YR`/`SALE_MO`. `doc_id` = `CLERK_NO` or `OR_BOOK-OR_PAGE` or `SALE_ID_CD`.

Grantee is empty. Headline flow uses `require_named_grantee=False`. Entity-buyer **shares are not identified** from the free file; publish sale counts and the caveat. Do not pretend current GIS owner is the buyer. County PA BBS sales files ($50) stay out of scope.

Coverage window **2000–2025** when yearly SDFs are stacked. A single assessment-year file still runs through that window.

## Consequences

GIS is the stock source of truth (folio points). SDF cannot support an NYC-style entity-buyer headline. `sfr_1_4` includes Florida 2–4 flats inside official 2–9 codes. GIS timed 2026-09-18 (~15 min, 944 pages after fixing the silent 1000-row page cap); stays laptop-only until a local SDF exists.
