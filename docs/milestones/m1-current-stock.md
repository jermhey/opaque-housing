# Milestone 1: Current-stock baseline (rules only)

Date: 2026-09-16. Metro: NYC. PLUTO **26v2**. Rules `2026-09-16.1`.

## What was built

- Name normalization and an ordered rules classifier (`R001`–`R999`)
- `oh ingest` for PLUTO `64uk-42ks` and tract–NTA `hm78-6dwm`
- `oh build` → classified parcels + stock tables under `data/derived/nyc/` (local only)
- `oh label` + a 600-row stratified queue at `eval/gold/queue.csv` (gitignored)
- `oh eval` + a synthetic CI gold file (`eval/gold/ci_dev.csv`, test-split macro-F1 = 1.0)

## Verified vs assumed

| Item | Status |
|---|---|
| PLUTO row count 858,284 and fields used in `$select` | Verified on 2026-09-16 extract (67,098,962 bytes) |
| Tract–NTA 2,327 rows | Verified (197,482 bytes) |
| Residential filter before/after | Verified in run manifest: 858,284 → 770,593 |
| Private denominator | Verified: 770,593 → 767,897 (`public` + `nonprofit_religious` out) |
| Co-op buildings counted as entity-owned | They are not. Entity share on `coop_building` is 0 |
| PLUTO condo rows are unit owners | They are not (billing lots). `condo_unit` shares are complex-level |
| Confusion-matrix correction of citywide shares | Harness exists; **not applied**. Waiting on hand labels |
| Bootstrap intervals | Implemented as a function; not run on 768k parcels in this build |

## Raw headline shares (uncorrected)

Private residential lots only. **Entity-owned** = LLC + corp + partnership. Trusts are a sensitivity series only.

| Series | Parcels | Units | Entity parcel share | Entity unit share |
|---|---:|---:|---:|---:|
| Private, entity only | 767,897 | 3,530,373 | **15.3%** | **39.2%** |
| Private, entity + trust | 767,897 | 3,530,373 | 22.3% | 42.0% |
| `sfr_1_4` + `condo_unit`, entity only | 659,629 | 1,219,592 | **7.8%** | **11.5%** |
| `sfr_1_4` + `condo_unit`, entity + trust | 659,629 | 1,219,592 | 15.5% | 18.5% |

These are **raw rule assignments**. Do not treat them as the published finding until the gold set is labeled and the Rogan–Gladen correction is applied.

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

## Gold set (gate for you)

A 600-name queue is at `eval/gold/queue.csv` (295 dev / 305 test), stratified by rule, borough, and building type. Individuals, trusts, estates, and unknowns are also copied to `eval/gold/individuals/` and are gitignored.

Label it:

```bash
uv run oh label
```

Accepted values are the `OwnerClass` strings (`individual`, `llc`, `corp`, …). `s` skips, `q` saves and quits.

Until that file is labeled, **corrected shares and intervals are not available**. The synthetic CI file is not a substitute.

## Open questions

None that block M1 engineering. The remaining M1 done-when item is your labels.

## What this milestone is not

- No ACRIS flow or historical stock (M2)
- No LLM fallback, HPD, or DOS opacity tiers (M3)
- No public site (M4)
- No GitHub remote yet (`gh` is not logged in)
