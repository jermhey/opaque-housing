# Milestone 2: Flow and history

Date: 2026-09-17. Metro: NYC. ACRIS extract 2026-09-17. Rules `2026-09-16.2`. Window: recorded years **2003–2025** (ADR 0006).

## What was built

- ACRIS adapter (Master `bnx9-e6tj`, Legals `8h5j-fqxa`, Parties `636b-3b5g`) with snapshot dedup on `good_through_date`
- Official-code sale-deed map and arm's-length filter (ADR 0005)
- PAD billing↔unit mapper (fixture-tested; no live PAD file — SODA 403, zip URLs 404)
- `oh ingest --dataset acris` (paged SODA → parquet) and `oh flow`
- Entity-buyer series by year / borough / building type; sensitivity table; reconstructed year-end stock; PLUTO consistency check

## Verified vs assumed

| Item | Status |
|---|---|
| Sale codes from official `7isb-wh4c` | Verified. Headline set: `DEED`, `DEED, RC`, `DEEDP`, `DEEDO`, `REIT`, `ASTU` |
| Consideration usable from 2003 | Verified. `DEED` `document_amt ≥ 10000` is 0–7/year before 2003; 31,695 of 51,337 in 2003 |
| `document_id` is `YYYYMMDD` from 2003 | Verified. Earlier IDs are `BK_` / `FT_` |
| Party names in the window | Verified on 40-doc `DEED` samples 1985–2024 (40/40 named grantees) |
| Property borough is Legals `borough` | Verified. Master `recorded_borough` is the recording office |
| Staten Island in the headline flow | **Almost absent.** SI legal rows exist (208,179), but a sample of their `document_id`s are `RPTT` (transfer tax), not `DEED`. `RPTT` is official class `OTHER DOCUMENTS` and is `other` under ADR 0005. 194,407 unique SI legal docs overlap our sale-type Master extract in **1** row |
| Condo unit lots | Not in the flow universe. No live PAD. `condo_unit` sales in the year×type table are 1–17/year |
| Building type / units on history | Current PLUTO 26v2 attributes, not historical use |
| Gold correction on flow | Not applied. Buyer-name confusion is not the stock gold set |

## Extract and filter counts

| Stage | In | Out |
|---|---:|---:|
| Master snapshot dedup | 1,642,007 | 1,638,258 |
| Parties snapshot dedup | 25,464,157 | 25,387,936 |
| Parties grantor/grantee only | 25,387,936 | 25,341,311 |
| Named `sale_deed` (history set) | 1,473,996 | 1,473,135 |
| `document_amt ≥ $10,000` (flow set) | 1,473,135 | 923,819 |
| Join to current residential PLUTO | 923,819 | 558,182 |
| Drop 2026 (partial year) | — | **546,257** headline sales |

History (no amount cut) joins 990,195 of 1,473,135 named sale deeds to a current residential lot.

## Headline flow (2003–2025 pooled)

Arm's-length = `sale_deed` + named grantee + `document_amt ≥ $10,000`. Entity buyer = LLC + corp + partnership. Trusts are out of the headline.

| Series | Sales | Units | Entity sale share | Entity unit share |
|---|---:|---:|---:|---:|
| Private residential (PLUTO-matched) | 546,257 | 2,199,598 | **24.2%** | **59.6%** |
| `sfr_1_4` + `condo_unit` | 473,935 | 842,143 | **16.7%** | **19.1%** |

The citywide unit share is high because large multifamily and mixed-use sales are mostly entity buyers (often 85–90% of those sales). The informative series is the `sfr_1_4` + `condo_unit` row — and in this extract that row is almost entirely `sfr_1_4`.

## Entity-buyer share by recorded year

| Year | All res. sale share | SFR+condo sale share |
|---|---:|---:|
| 2003 | 16.7% | 11.7% |
| 2006 | 13.3% | 7.3% |
| 2010 | 21.5% | 15.5% |
| 2015 | 34.4% | 23.7% |
| 2020 | 26.5% | 19.8% |
| 2021 | 23.4% | 16.1% |
| 2024 | 33.2% | 25.5% |
| 2025 | **36.5%** | **29.2%** |

Trough in the mid-2000s, rise through 2014–15, COVID dip, then a new high in 2024–25. 2021 SFR+condo entity *purchase* share (16.1%) is in the same neighborhood as NAR’s 2021 national institutional-purchase figure (13.2%) — different geography and a legal-form definition, not a match we tuned to.

## Sensitivity (pooled 2003–2025, same residential join)

| Config | Sales | Entity sale share |
|---|---:|---:|
| Default `$10k` | 546,257 | 24.2% |
| Threshold `$0` | 964,947 | 21.3% |
| Threshold `$1` | 569,537 | 24.2% |
| Threshold `$100k` | 535,431 | 23.8% |
| Treat `$0` as missing, then `$10k` | 941,661 | 21.2% |
| Exclude same first token (LAST FIRST) | 523,483 | 24.1% |
| Require `percent_trans = 100` | 541,893 | 24.2% |
| Drop `ASTU` | 546,255 | 24.2% |
| Drop `DEEDO` | 534,022 | 24.0% |

The amount cut changes the **count** more than the **share**. Including zero-amount deeds adds mostly non-entity transfers (family / unreported consideration). `ASTU` is negligible without PAD. Same-surname and full-interest switches barely move the headline.

## Reconstructed historical stock

Owner-at-year-end = latest named `sale_deed` on that parcel on or before 31 Dec, **no amount cut**. Universe is parcels with at least one such deed that joins current PLUTO. That is **not** a full-city stock.

| Year-end | Parcels | Coverage of PLUTO res. lots | Entity unit share | SFR+condo entity unit share |
|---|---:|---:|---:|---:|
| 2003 | 43,332 | 5.6% | 46.9% | 8.5% |
| 2010 | 269,576 | 35.0% | 50.1% | 5.7% |
| 2015 | 348,519 | 45.3% | 53.8% | 8.4% |
| 2020 | 416,502 | 54.1% | 54.8% | 11.1% |
| 2025 | 476,496 | 61.9% | 54.9% | 13.6% |

Citywide reconstructed entity *unit* share is ~55% by the 2010s because the parcels that turn over include large buildings. Current PLUTO private entity unit share (M1, all lots) is 39.2% raw — lower, because lots with no post-2003 ACRIS sale stay out of this reconstruction and are disproportionately 1–4 family.

## Consistency vs PLUTO (as of 2026-08-01)

| | |
|---|---:|
| PLUTO residential lots | 770,593 |
| Reconstructed (latest sale deed) | 483,585 |
| Compared | 483,585 |
| PLUTO lots with no matching deed | 287,008 |
| Owner-class agreement | **97.3%** |
| Entity-flag agreement | **99.1%** |

By building type, `sfr_1_4` agrees at 97.9% class / 99.7% entity. `condo_unit` class agreement is 0.6% (n=164) — billing-lot association name vs unit buyer. `coop_building` class agreement is 37.2% (n=575). Those two grains are the known PLUTO traps (ADR 0002).

## Open questions

- **Should `RPTT` count as a sale deed, at least on Staten Island?** Official description is NYC real property transfer tax; parties are grantor/seller and grantee/buyer. Leaving it in `other` drops SI from flow. Changing this is a new ADR, not a silent retune.
- Live PAD extract still missing. Condo unit sales stay out until that file is on disk.
- Apply the stock gold confusion matrix to buyer names? The gold set is PLUTO owners, not ACRIS grantees.

## What this milestone is not

- No LLM fallback, HPD, or DOS opacity tiers (M3)
- No public site (M4)
- No Philadelphia adapter (M5)
- No gold-corrected flow shares

Do not start M3 until confirmed.
