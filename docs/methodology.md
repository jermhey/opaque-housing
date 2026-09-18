# Methodology

Definitions live in [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) §3. This file records how those definitions are implemented, plus sources for external sanity checks.

## Names-only LLM constraint

Prompts receive owner **names only**. Addresses and other personal context are not sent. Model ID comes from `ANTHROPIC_MODEL` (never hardcoded). Prompt version `2026-09-17.1` asks for JSON `{owner_class, rationale}` at temperature 0.

Only `R999_unknown` names are sent. First-match rules have no conflict path. Results are cached in DuckDB on `(owner_key, prompt_version, model_id)`. A USD cost cap and a max-name cap abort the run (`OH_LLM_COST_CAP`, `OH_LLM_MAX_NAMES`). The test split is never used to tune the prompt. `oh eval --with-llm` writes rules-only and rules+LLM macro-F1 side by side.

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
- a later slash part that is exactly `LWT` / `EST` / `ESTATE` / `DEF` (not `DEFT`) assigns `estate` (`R051`)
- wrapped `TR UST` is canonicalized to `TRUST`
- `owner_key` is `sha256(name_normalized)[:16]` of the first party

## Owner-class rules (`RULES_VERSION = 2026-09-17.3`)

First match wins. Each rule has a positive and a negative unit test.

| rule_id | class | Test |
|---|---|---|
| `R001_blank` | `unknown` | empty after normalize |
| `R010_hdfc` | `hdfc` | `HDFC` or `HOUSING DEVELOPMENT FUND` |
| `R020_public` | `public` | Agency phrases (`CITY OF NEW YORK`, `NYCHA`, `CITY OF PHILADELPHIA`, `HOUSING AUTH` / `HOUSING AUTHORITY`, `NYS OFFICE`, …). Not bare `USA`/`NYS`/`FEDERAL`. Not an LLC. `CITY COLLEGE` is public (CUNY). |
| `R030_lender` | `lender_reo` | GSEs, `BANK`, `MORTGAGE`, `REO`, `J P MORGAN CHASE`. Not standalone `NA` or `CHASE`. Not an LLC. |
| `R040_nonprofit` | `nonprofit_religious` | church/university/hospital/ministry tokens — not `COLLEGE AVE` / `COLLEGE POINT`, not an LLC, not `CHURCH`+`REALTY` |
| `R050_estate` | `estate` | starts with `ESTATE`, or `ESTATE OF` / `EST OF` — not `REAL ESTATE`, not if INC/LLC/CORP |
| `R051_estate_suffix` | `estate` | later slash part is `LWT` / `EST` / `DEF` (ADR 0004 amendment) |
| `R060_trust` | `trust` | `TRUSTEE`, `TRUST`, or a trailing ` TR` |
| `R070_coop_building` | `coop_corp` | official `coop_building` type, regardless of name |
| `R071_coop_name` | `coop_corp` | `CO-OP` / `COOPERATIVE` / `TENANTS CORP` / `OWNERS CORP` on a non-coop lot — not if the name is an LLC |
| `R080_llc` | `llc` | `LLC` |
| `R090_partnership` | `partnership` | `LP` / `LLP` / `LLLP` / partnership phrases |
| `R100_corp` | `corp` | `CORP` / `INC` / `LTD` / `LIMITED` / `PC` / `COMPANY` / `CO` / `PLC`, or `CORP` glued to the previous word (`OPERATINGCORP`) |
| `R110_individual` | `individual` | `ET AL` / `JTWROS` / `&` households (only if the stem is person-like), or 2–5 alphabetic tokens, hyphens allowed, without entity/`CONDOMINIUM` words |
| `R999_unknown` | `unknown` | everything else, including blank-looking trade names such as `ACME REALTY` |

Unmatched names stay `unknown` and stay in the private denominator until the LLM fallback (`oh eval --with-llm` / optional live classify). The test split is not used to retune rules or the prompt.

## Stock metrics

- **Entity-owned** = `llc` + `corp` + `partnership`. Trusts are a sensitivity series only.
- **Private denominator** drops `public` and `nonprofit_religious` (`exclude_public_nonprofit`). Co-ops, HDFCs, estates, lenders, unknowns, and individuals remain.
- Shares are computed **parcel-weighted** and **unit-weighted**.
- Cross-tabs: citywide by class; by building type; borough × type; NTA × type.
- NTA cells with fewer than 10 residential units have shares nulled (`suppressed=true`). Rows are not dropped.
- The informative series is entity share of `sfr_1_4` + `condo_unit`.

## Misclassification correction

When a labeled gold set exists, binary entity vs. not-entity sensitivity and specificity are applied with a Rogan–Gladen correction to each headline share. Entity-plus-trust series use a separate binary that treats `trust` as positive. Correction uses the **test** split only (`n=305`). Intervals are percentile bootstrap of the gold pairs (1,000 resamples); citywide `p_hat` is treated as a census.

CI still uses the synthetic file (`eval/gold/ci_dev.csv`) and fails if test-split macro-F1 falls below `eval/reports/baseline_macro_f1.json`.

The same name-level confusion matrix is applied to unit-weighted and `sfr_1_4`+`condo_unit` series. That assumes misclassification rates do not vary by building size or type. The gold set is stratified by rule, not a simple random sample of lots, so the binary rates are an approximation.

## External sanity checks

These are **different quantities** from this project's stock shares. Direction and rough magnitude only. We do not tune rules or corrections to match them.

- **NAR (2022), using Black Knight deeds.** “Institutional” = company / corporation / LLC on the deed. 13.2% of U.S. residential *purchases* in 2021 (11.8% in 2020). This is a **flow** metric with a legal-form definition close to our entity headline, not a stock share, and it is national. [Impact of Institutional Buyers on Home Sales and Single-Family Rentals](https://www.nar.realtor/sites/default/files/documents/2022-impact-of-institutional-buyers-on-home-sales-and-single-family-rentals-05-12-2022.pdf).
- **CoreLogic (Malone, 2023).** Investor share of U.S. *single-family purchases* about 26–27% in spring/summer 2023 (28.7% in December 2023). “Investor” is a buyer-type / occupancy construct, not LLC vs person. [Summary](https://nationalmortgageprofessional.com/news/us-home-investor-share-remained-high-early-summer-2023).
- **Urban Institute (2023).** Entities owning ≥100 one-unit rentals held about 574,000 homes as of June 2022, **3.8%** of 15.1 million one-unit rentals. This is **portfolio size**, not legal form; most entity owners in our data would not meet the 100-home cutoff. [A Profile of Institutional Investor-Owned Single-Family Rental Properties](https://www.urban.org/sites/default/files/2023-08/A%20Profile%20of%20Institutional%20Investor%E2%80%93Owned%20Single-Family%20Rental%20Properties.pdf).
- **Harwood, Ellen, and O’Regan (Furman Center).** NYC multifamily *corporate vs non-corporate* landlords, 2012–2023, for tenant-outcome differences — not a citywide ownership share. Useful as a local corporate-landlord literature pointer. [The Rise of Corporate Landlords](https://www.furmancenter.org/news/examining-the-behavioral-differences-of-corporate-landlords/).

Our informative series (entity share of `sfr_1_4` + `condo_unit` **stock**) is not comparable to the national purchase-flow figures. M2 flow metrics are the right place to put them side by side.

## Arm's-length sale filter (M2)

Canonical `doc_type` mapping is ADR 0005. Official codes only.

- **`sale_deed`:** `DEED`, `DEED, RC`, `DEEDP`, `DEEDO`, `REIT`, `ASTU`
- **`nonsale_deed`:** other `DEEDS AND OTHER CONVEYANCES` (correction, confirmatory, TOD, in-rem, life estate, timeshare, contract, lease, easement, condo declaration, …)
- **`other`:** mortgages, UCC, everything else

A flow-metric sale is a `sale_deed` with a named grantee (`party_type=2`) and `document_amt >= 10000`. Zero consideration fails the default cut. Sensitivity: `$0` / `$1` / `$10k` / `$100k`, treat-zero-as-missing, drop `ASTU` or `DEEDO`, same-surname exclusion, require `percent_trans=100`. `percent_trans=0` is unspecified, not a 0% interest.

Historical stock uses every `sale_deed` with a named grantee (no amount cut). Buyer class is the first named grantee, name-only — parcel `building_type` is not passed into the buyer rules.

Coverage window: recorded years **2003–2025** (ADR 0006). Year is `recorded_datetime`. Property borough is Legals `borough`. Snapshot rows are collapsed to the latest `good_through_date`.

Condo unit lots map through DCP PAD (`billboro` / `billblock` / `billlot` and the official lo–hi range). A mapped unit counts as `condo_unit` with 1 unit, not the billing-lot complex size. Without a PAD file, only exact-BBL PLUTO matches enter the residential universe.

Staten Island is effectively out of the headline flow. SI legal lots exist, but the linked Master rows in a live sample are `RPTT` (NYC real property transfer tax), which ADR 0005 leaves as `other`. Treating `RPTT` as a sale is an open question, not a silent retune.

## Opacity tiers (M3)

Entity-owned private residential owners only (`llc` + `corp` + `partnership`). Trusts stay a sensitivity series and do not get a tier. Rules version `OPACITY_VERSION = 2026-09-17.1` (ADR 0007):

| rule_id | Tier | Test |
|---|---|---|
| `T010_hpd_person` | O1 | HPD `HeadOfficer` / `IndividualOwner` / `JointOwner` / `Officer` / `Shareholder` with first+last |
| `T020_dos_chairman` | O1 | NY DOS `chairman_name` classifies as `individual` |
| `T030_cluster_o1` | O2 | No own person; another cluster member is O1 |
| `T040_entity_chain` | O4 | No person; HPD `CorporateOwner` or DOS process name is a *different* entity |
| `T050_no_person` | O3 | Residual |

`agent_address_only` is evidence, not a gate. Agent / SiteManager / Lessee names are not O1 and are not person-links.

Portfolio links (ADR 0008): cluster edges are shared O1 persons and HPD `CorporateOwner` exact names, among **entity** owners only. Shared addresses and seed agent names still set `agent_address_only` / the denylist; they are not union-find edges (address + officer mixing collapsed the graph). The top-20 cluster review lists **entity names only**.

## Philadelphia stock (M5)

OPA `opa_properties_public` via Carto. Residential filter and unit lower bounds are ADR 0010. `geo_borough` is `Philadelphia`; `geo_neighborhood` is ZIP; `geo_tract` is null. Classify `owner_1` only. Parcel share is the NYC vs PHL headline. PA DOS `3urc-uaba` has no officer names, so PHL has no O-tiers.

PHL flow uses `rtt_summary` sale types `DEED` / `DEED SHERIFF` / `SHERIFF'S DEED`, the same $10,000 named-grantee cut as NYC, and recorded years **2000–2025**.

## Public aggregates (M4)

`oh publish` copies an allowlist of citywide and NTA-or-coarser files. Parcel extracts, `owner_key`, HPD person names, addresses, and cluster member lists are refused. NTA cells with fewer than 10 units keep `suppressed=true`. The static site reads `site/data/site.json`. GitHub-hosted refresh updates PLUTO stock only; ACRIS and NY DOS are not cold-pulled (ADR 0009).
