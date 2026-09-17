# Methodology

Definitions live in [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) §3. This file records how those definitions are implemented, plus sources for external sanity checks.

## Names-only LLM constraint

When the LLM fallback lands (M3), prompts will receive owner **names only**. Addresses and other personal context are not sent. Model ID comes from `ANTHROPIC_MODEL`.

## Building-type map (NYC)

Canonical types are assigned from official DOF building-class codes (plus DCP's PLUTO-only condo rollup codes) and `unitsres` / `landuse`. Co-ops are those official classes whose published label is a cooperative (`C6`, `D4`, `A8`, …), never a name match. See `src/opaque_housing/adapters/nyc/building_type.py` and `docs/data_sources.md`.

`parcels_snapshot` is **residential lots only** (ADR 0003). The filter records before/after counts (`pluto_residential_only`).

PLUTO condo rows are billing-lot / complex grain, not unit owners (ADR 0002). Owner mailing addresses are not taken from PLUTO; clustering uses ACRIS/HPD later.

## Name normalization (M1)

`RULES_VERSION` is independent of normalization. Current behavior (`src/opaque_housing/normalize/names.py`):

- uppercase; `.` and `,` become spaces; other punctuation is stripped; whitespace collapsed
- LLC / trust / corporation phrases are canonicalized (`L.L.C.` → `LLC`, `TTEE` → `TRUSTEE`, `INCORPORATED` → `INC`)
- multiple owners split on `/` only; `&` stays one household (ADR 0004)
- classification uses the first slash-separated party
- `owner_key` is `sha256(name_normalized)[:16]`

## Owner-class rules (`RULES_VERSION = 2026-09-16.1`)

First match wins. Each rule has a positive and a negative unit test.

| rule_id | class | Test |
|---|---|---|
| `R001_blank` | `unknown` | empty after normalize |
| `R010_hdfc` | `hdfc` | `HDFC` or `HOUSING DEVELOPMENT FUND` |
| `R020_public` | `public` | NYC/state/federal housing-authority phrases |
| `R030_lender` | `lender_reo` | GSEs, `BANK OF`, `NA`, `MORTGAGE`, `REO`, … — not if the name is an LLC |
| `R040_nonprofit` | `nonprofit_religious` | church/university/hospital tokens — not `COLLEGE POINT` |
| `R050_estate` | `estate` | starts with `ESTATE`, or `ESTATE OF` / `EST OF` — not `REAL ESTATE` |
| `R060_trust` | `trust` | `TRUSTEE`, `TRUST`, or a trailing ` TR` |
| `R070_coop_building` | `coop_corp` | official `coop_building` type, regardless of name |
| `R071_coop_name` | `coop_corp` | `CO-OP` / `COOPERATIVE` / `TENANTS CORP` / `OWNERS CORP` on a non-coop lot |
| `R080_llc` | `llc` | `LLC` |
| `R090_partnership` | `partnership` | `LP` / `LLP` / `LLLP` / partnership phrases |
| `R100_corp` | `corp` | `CORP` / `INC` / `LTD` / `PC` / `COMPANY` / `CO` / `PLC` |
| `R110_individual` | `individual` | `ET AL` / `JTWROS` / `&` households, or 2–5 alphabetic tokens without entity words |
| `R999_unknown` | `unknown` | everything else, including blank-looking trade names such as `ACME REALTY` |

Unmatched names stay `unknown` and stay in the private denominator. They are not sent to an LLM in M1.

## Stock metrics

- **Entity-owned** = `llc` + `corp` + `partnership`. Trusts are a sensitivity series only.
- **Private denominator** drops `public` and `nonprofit_religious` (`exclude_public_nonprofit`). Co-ops, HDFCs, estates, lenders, unknowns, and individuals remain.
- Shares are computed **parcel-weighted** and **unit-weighted**.
- Cross-tabs: citywide by class; by building type; borough × type; NTA × type.
- NTA cells with fewer than 10 residential units have shares nulled (`suppressed=true`). Rows are not dropped.
- The informative series is entity share of `sfr_1_4` + `condo_unit`.

## Misclassification correction

When a labeled gold set exists, binary entity vs. not-entity sensitivity and specificity are applied with a Rogan–Gladen correction to each headline share. CI uses a synthetic file (`eval/gold/ci_dev.csv`) and fails if test-split macro-F1 falls below `eval/reports/baseline_macro_f1.json`.

Corrected citywide headlines are **not** published until the hand-labeled ~600-name set exists. The harness is in place; the labels are not.

## External sanity checks

Not started. Citations will be added here; we will not tune results to match them.

## What will be documented here later

- Arm's-length sale filter and sensitivity parameters
- Opacity-tier tests and evidence fields
- LLM prompt version
- Citations for published investor-purchase research
