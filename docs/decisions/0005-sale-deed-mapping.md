# ADR 0005: ACRIS sale-deed mapping and arm's-length filter

Status: accepted (2026-09-17)

## Context

Milestone 2 needs a canonical `doc_type` of `sale_deed` | `nonsale_deed` | `other`, plus the brief's arm's-length tests (deed-type, consideration above a threshold, not intra-family / transfer-to-own-trust / correction). Codes come from the official Document Control Codes table (`7isb-wh4c`, committed as `acris_document_control_codes.csv`). Live Master counts were read on 2026-09-17 (`bnx9-e6tj`).

## Decision

### Type mapping

A Master `doc_type` is `sale_deed` only if it is one of these official conveyance codes:

| `doc__type` | Official description | Live rows (raw, incl. snapshot dups) |
|---|---|---:|
| `DEED` | DEED | 3,650,964 |
| `DEEDO` | DEED, OTHER | 30,160 |
| `ASTU` | UNIT ASSIGNMENT | 2,337 |
| `DEED, RC` | DEED WITH RESTRICTIVE COVENANT | 477 |
| `DEEDP` | DEED, PRE RPT TAX | 2 |
| `REIT` | REAL ESTATE INV TRUST DEED | 0 |

Every other code whose official `class_code_description` is `DEEDS AND OTHER CONVEYANCES` is `nonsale_deed`. That includes correction/confirmatory (`CORRD`, `CONDEED`, `DEED COR`), death/estate forms (`TODD`, `RTOD`, `IDED`, `DEED, LE`), timeshare (`DEED, TS`), contracts (`CNTR`), leases/easements/air rights/condo declarations, and the rest of that class.

Everything outside that class (`MTGE`, UCC, …) is `other`.

### Arm's-length sale (flow metric)

A transfer is an arm's-length sale when all of these hold:

1. `doc_type_canonical = sale_deed`
2. A named grantee exists (`party_type = 2` and non-blank `name`, after snapshot dedup)
3. Consideration is usable and at least `$10,000`

`document_amt = 0` **fails** the default threshold. It is not treated as missing. Sensitivity runs: `$0`, `$1`, `$10,000`, `$100,000`, and “treat zero as missing then apply `$10,000`”.

Intra-family (same last token, both names classify as `individual`) and “require `percent_trans = 100`” are **sensitivity-only**. They are off by default.

`percent_trans = 0` is the modal value on `DEED` (2,322,457 raw rows) and is treated as *unspecified*, not a 0% interest. `100` is full interest (1,309,673). Partials (`50`, `25`, …) stay in the default series.

### Historical stock

Reconstructed owner-at-date uses **every `sale_deed` with a named grantee**, not the `$10,000` cut. Applying the flow filter here would punch holes in the chain and keep a prior owner after a $0-amount recording. Sensitivity reconstructs from the arm's-length subset as well.

Buyer class is taken from the **first named grantee** (sorted by name for stability). Classification is name-only: we do not pass the parcel’s `building_type` into the buyer rules, so an LLC that buys a co-op *building* stays `llc` (`R070` must not fire on the buyer).

### What we are not deciding here

- Coverage years: ADR 0006.
- Condo billing ↔ unit lots: PAD mapper; exact-BBL join when PAD is absent.
- `party_type = 3` (46,823 rows; sample names look like people). Not grantor or grantee.

## Why

The brief’s examples of “not a sale” match official labels: correction, confirmatory, contract of sale, lease, easement, in-rem, transfer-on-death, life estate, timeshare. `ASTU` is a unit assignment with grantor/grantee parties — a condo-unit conveyance, not a declaration. `DEEDO` is “deed, other” and is kept in the headline set; sensitivity can drop it.

The `$10,000` default is the brief’s starting threshold. Live data show it is meaningless before 2003 (ADR 0006).

## Consequences

- Flow undercounts LLC membership-interest transfers (no deed). Already an honest-limits item.
- $0-amount deeds after 2003 are excluded from the headline flow series and included in historical stock. Many are family/trust transfers; some are market sales with consideration only on the RPTT form. Both series are published.
- Changing the sale-code set is a new ADR, not a silent retune.
