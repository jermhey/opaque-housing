# Milestone 1: Current-stock baseline (rules only)

Date: 2026-09-16. Metro: NYC. PLUTO **26v2**. Rules `2026-09-16.2` (dev-only retune after gold).

## What was built

- Name normalization and an ordered rules classifier (`R001`–`R999`)
- `oh ingest` for PLUTO `64uk-42ks` and tract–NTA `hm78-6dwm`
- `oh build` → classified parcels + stock tables under `data/derived/nyc/` (local only)
- `oh label` + a 600-row stratified queue at `eval/gold/queue.csv` (gitignored), now fully labeled
- `oh eval` + a synthetic CI gold file (`eval/gold/ci_dev.csv`, test-split macro-F1 = 1.0)
- Test-split Rogan–Gladen correction with bootstrap intervals in `data/derived/nyc/headlines.json`

## Verified vs assumed

| Item | Status |
|---|---|
| PLUTO row count 858,284 and fields used in `$select` | Verified on 2026-09-16 extract (67,098,962 bytes) |
| Tract–NTA 2,327 rows | Verified (197,482 bytes) |
| Residential filter before/after | Verified in run manifest: 858,284 → 770,593 |
| Private denominator | Verified: 770,593 → 768,516 (`public` + `nonprofit_religious` out). Wider than 16.1 because bare `USA`/`NYS` no longer pull private firms into `public` |
| Co-op buildings counted as entity-owned | They are not. Entity share on `coop_building` is 0 |
| PLUTO condo rows are unit owners | They are not (billing lots). `condo_unit` shares are complex-level |
| Confusion-matrix correction of citywide shares | Applied. Test-split Rogan–Gladen, n=305. See corrected table below |
| Bootstrap intervals | 1,000-resample percentile CI on gold-set sens/spec. Citywide `p_hat` treated as a census |

## Raw headline shares (uncorrected)

Private residential lots only. **Entity-owned** = LLC + corp + partnership. Trusts are a sensitivity series only.

| Series | Parcels | Units | Entity parcel share | Entity unit share |
|---|---:|---:|---:|---:|
| Private, entity only | 768,516 | 3,535,741 | **15.4%** | **39.2%** |
| Private, entity + trust | 768,516 | 3,535,741 | 22.4% | 42.0% |
| `sfr_1_4` + `condo_unit`, entity only | 659,875 | 1,220,134 | **7.8%** | **11.5%** |
| `sfr_1_4` + `condo_unit`, entity + trust | 659,875 | 1,220,134 | 15.6% | 18.5% |

These are **raw rule assignments**. Corrected headlines are in the next table.

## Corrected headline shares (test-split Rogan–Gladen)

Gold set labeled 2026-09-17. Rules then retuned on the **dev** split only (`2026-09-16.2`). Correction uses the **test** split only. Entity sensitivity 97.4%, specificity 97.8%. Intervals are 95% percentile bootstrap of the labeled pairs.

| Series | Weight | Raw | Corrected | 95% CI |
|---|---|---:|---:|---|
| Private, entity only | units | 39.2% | **38.9%** | 37.0–41.0% |
| Private, entity only | parcels | 15.4% | **13.8%** | 11.9–15.5% |
| Private, entity + trust | units | 42.0% | **42.7%** | 40.6–44.9% |
| Private, entity + trust | parcels | 22.4% | **21.7%** | 19.5–23.5% |
| `sfr_1_4` + `condo_unit`, entity only | units | 11.5% | **9.8%** | 7.7–11.4% |
| `sfr_1_4` + `condo_unit`, entity only | parcels | 7.8% | **5.9%** | 3.8–7.6% |
| `sfr_1_4` + `condo_unit`, entity + trust | units | 18.5% | **17.5%** | 15.3–19.3% |
| `sfr_1_4` + `condo_unit`, entity + trust | parcels | 15.6% | **14.4%** | 12.1–16.1% |

After the retune, raw and corrected citywide unit shares agree. The correction now *lowers* the small-building series (11.5% → 9.8%) because remaining errors are more false entity calls than misses. Test-split rules macro-F1 = 0.91 (was 0.79). Dev accuracy 98.0%; six residuals left on purpose (trade-name individuals, `LIFESPIRE`, official coop lots whose names look like addresses).

Caveats: the same name-level confusion matrix is applied to unit-weighted and small-building series. The gold set is stratified by rule, not a simple random sample of lots. Misclassification is probably worse on large buildings with trade names, so the 45.0% citywide unit figure may still be low.

### Entity unit share by building type (private, entity only)

| Building type | Private parcels | Private units | Entity unit share |
|---|---:|---:|---:|
| `large_mf` | 13,486 | 748,095 | 73.4% |
| `small_mf` | 29,872 | 246,308 | 70.6% |
| `mixed_use_res` | 55,545 | 853,806 | 60.9% |
| `condo_unit` (billing lot) | 6,402 | 121,341 | 23.1% |
| `sfr_1_4` | 653,227 | 1,098,251 | 10.2% |
| `coop_building` | 7,202 | 459,886 | 0.0% |

Large multifamily is mostly entity-owned, as expected. The informative series is the `sfr_1_4` + `condo_unit` row in the headline table.

### Entity unit share by borough (private, entity only)

| Borough | Private parcels | Private units | Entity unit share |
|---|---:|---:|---:|
| Bronx | 75,617 | 531,495 | 48.2% |
| Manhattan | 32,551 | 892,192 | 45.6% |
| Brooklyn | 249,965 | 1,058,661 | 42.3% |
| Queens | 297,578 | 872,642 | 29.1% |
| Staten Island | 112,186 | 175,383 | 11.5% |

Manhattan’s **parcel** entity share is 52.4% because many lots are large multifamily; its unit share is 45.6%.

### Owner-class counts (all residential lots)

| Class | Parcels | Units |
|---|---:|---:|
| individual | 563,327 | 1,222,028 |
| llc | 95,079 | 1,078,347 |
| trust | 53,833 | 99,011 |
| unknown | 22,665 | 252,485 |
| corp | 20,571 | 255,856 |
| coop_corp | 6,713 | 449,528 |
| hdfc | 3,424 | 120,935 |
| partnership | 1,668 | 50,688 |
| nonprofit_religious | 1,412 | 20,633 |
| public | 1,284 | 185,639 |
| lender_reo | 518 | 1,179 |
| estate | 99 | 316 |

Unknown is 2.9% of residential parcels but 252,485 units — large buildings with trade names that are not legal-form tokens. Blank names are 368 lots (`R001_blank`).

NTA × building-type cells: 5,802 rows, 251 suppressed (< 10 units). 229 private lots have a null NTA.

## Gold set

600 rows labeled (596 unique `owner_key`s; NYCHA and DCAS each appear twice). 295 dev / 305 test. Local only: `eval/gold/queue.csv`.

Test-split rules macro-F1 = 0.79. Weak classes: `public` (USA/NYS token), `lender_reo` (`NA` as a name), `unknown` (hyphens and wrapped `TR UST`). Do not retune on the test split.

### Low-confidence review

| Name | First label | After review | Why |
|---|---|---|---|
| `MCFARLAND MICHAEL C REV` | `trust` | **`individual`** | `REV` is Reverend, not revocable |
| `SST HOME OWNERS CORP` | `corp` | **`coop_corp`** | `HOME OWNERS CORP` is the coop name pattern |
| `BUZ, FREDERICK H/LWT/DEF` | `estate` | `estate` | `LWT` is last-will; slash-split drops it from the classified token |
| `GEORGE BARBEE LIMITE` | `corp` | `corp` | truncated `LIMITED` |
| `CITY COLLEGE DORMS` | `public` | `public` | CUNY dorms; universities otherwise go `nonprofit_religious` |
| `KINGS 18 REALTY SAMUEL HALBERG` | `unknown` | `unknown` | trade name plus a person, no legal form |
| `123-125 HETT AVE OWNERS CORP` | `coop_corp` | `coop_corp` | name-based coop on an `sfr_1_4` lot |
| `1316 JG OWNERS CORP` | `coop_corp` | `coop_corp` | same |

## Open questions

- Should slash-split keep `LWT` / `DEF` suffixes as estate evidence? ADR 0004 currently classifies only the first party.
- Should CUNY / public-college housing be `public` or `nonprofit_religious`? We used `public` here.
- Apply a unit-weighted or building-type-specific confusion matrix later? The current correction is name-level and citywide.

## What this milestone is not

- No ACRIS flow or historical stock (M2)
- No LLM fallback, HPD, or DOS opacity tiers (M3)
- No public site (M4)
- No rule retune on the test split

Do not start M2 until confirmed.
