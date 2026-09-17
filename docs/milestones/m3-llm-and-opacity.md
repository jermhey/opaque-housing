# Milestone 3: LLM fallback and opacity

Date: 2026-09-17. Metro: NYC. HPD + DOS extracts 2026-09-17. Rules `2026-09-16.2`. Opacity `2026-09-17.1`. Prompt `2026-09-17.1`.

## What was built

- LLM fallback: names-only prompt, DuckDB cache, USD and max-name caps, `oh eval --with-llm`
- HPD adapter (`tesw-yqqr`, `feu5-w2e2`) and NY DOS adapter (`n9v6-gdp6` on data.ny.gov)
- `oh ingest --dataset hpd|dos|opacity` and `oh opacity`
- Portfolio clustering with a registered-agent denylist (ADR 0008)
- O-tier assignment with evidence (ADR 0007)
- Internal opacity shares and a logged top-20 cluster review (entity names only)

## Verified vs assumed

| Item | Status |
|---|---|
| HPD / DOS field names | Verified 2026-09-17 from live catalogs |
| HPD `type` fill rates | Verified. O1 types have first+last on ≥99% of rows. `CorporateOwner` is an entity name |
| DOS `chairman_name` / RA fill | Verified. CEO name 11.0%; registered agent 20.5% |
| DOS survivorship | Verified. Active table only; 4,281,406 rows ingested |
| DOS name match to PLUTO entities | **90.2%** (94,276 / 104,490 owner keys). Exact `normalize_name` only |
| LLM lift on the test split | **Not measured live.** No `ANTHROPIC_API_KEY` in this environment. 12 test names would have been sent (`R999`). Rules-only test macro-F1 **0.914**. Lift recorded as 0.00 / sent=0 / skipped=12 |
| Giant component | First run collapsed 28k entity owners. Cause: non-entity nodes + Agent corporation hubs + address edges. Fixed: entity nodes only; `exact_name` is `CorporateOwner` only; addresses are evidence, not edges. Largest component now **590** owners |

## Extract and filter counts

| Stage | In | Out |
|---|---:|---:|
| HPD registrations, valid BBL | 203,887 | 203,887 |
| Latest registration per BBL | 203,887 | 182,495 |
| HPD contacts loaded | 810,494 | 810,494 |
| Contacts on latest registration | 810,494 | 1,087,183 |
| NY DOS loaded | 4,281,406 | 4,281,406 |
| DOS exact-name match to entity owners | 4,281,406 | **94,276** |
| Private residential lots | 770,593 | 768,516 |
| Entity-owned (opacity universe) | 768,516 | **117,994** |

HPD contact join exceeds 810k because 132 registration IDs attach to more than one BBL. Rows are not dropped.

## Opacity-tier shares

Entity-owned = `llc` + `corp` + `partnership`. Trusts have no tier. O1 is a person on *that* owner’s HPD/DOS record, so the 92% citywide unit figure is **not** a clustering artifact.

| Series | Parcels | Units | O1 unit | O2 unit | O3 unit | O4 unit |
|---|---:|---:|---:|---:|---:|---:|
| Entity-owned private residential | 117,994 | 1,385,595 | **92.0%** | 0.02% | 7.0% | 0.9% |
| `sfr_1_4` + `condo_unit` | 51,551 | 140,352 | **63.9%** | 0.08% | 32.0% | 4.0% |

By building type (unit share):

| Type | O1 | O3 | Note |
|---|---:|---:|---|
| `large_mf` | 98.1% | 1.2% | HPD almost complete |
| `small_mf` | 97.0% | 1.9% | HPD almost complete |
| `mixed_use_res` | 91.6% | 5.7% | |
| `condo_unit` | 86.8% | 9.3% | Billing-lot grain (ADR 0002) |
| `sfr_1_4` | **58.3%** | **31.3%** | Many 1–4 family LLCs have no HPD person and no DOS CEO |

O2 is rare after the conservative graph (99 parcels). An entity without its own named person almost never shares *only* an officer/CorporateOwner with an O1 entity.

## Clusters

67,367 components among 104,490 entity owners. Two components ≥200 owners. Top-20 review: `eval/reports/cluster_review_top20.md`.

Cluster 1 (590 owners) is logged as a **likely false merge** (officer-name chain). Cluster 2 (BPP / PCV / Parker / Kips Bay) is a likely true holding structure. Cluster 10 includes `NYC HOUSING DEVELOPMENT CORP` and should not be read as a private empire.

## LLM

Module, cache, cost cap, and eval wiring are in the repo. Live Anthropic calls need `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`. Citywide there are 12,010 unknown parcels (9,898 owner keys) that would be eligible; that run was not started.

## Open questions

- **Person-name collisions.** First+last only. Cluster 1 is the test case for a degree cap or a second token (middle initial / address).
- **`HOUSING DEV FUND` vs `HOUSING DEVELOPMENT FU`.** Some HDFCs still classify as `corp` and enter the entity universe.
- Apply the stock gold matrix to buyer names? Still open from M2.
- Live PAD and Staten Island `RPTT` still open from M2.

## What this milestone is not

- No public site (M4)
- No Philadelphia adapter (M5)
- No live LLM labels on the test split or the citywide unknown set
- No concentration / HHI published as a headline (clusters are internal; cluster 1 is not a portfolio)

Do not start M4 until confirmed.
