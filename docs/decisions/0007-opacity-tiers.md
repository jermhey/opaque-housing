# ADR 0007: Opacity-tier evidence and residual O3

Status: accepted (2026-09-17)

## Context

Milestone 3 assigns O1–O4 to **entity-owned** private residential owners (`llc` + `corp` + `partnership` only). The brief’s O3 test is conjunctive (“no person **and** only registered-agent / law-firm / c/o addresses”). That leaves a hole: an LLC with a unique street address and no named person fits none of O1–O4. Every entity owner must get a tier; rows are not dropped.

HPD contact `type` values and fill rates were re-read from `feu5-w2e2` on 2026-09-17. NY DOS `chairman_name` (catalog label: CEO Name) is filled on 472,391 of 4,281,406 active rows (11.0%). `registered_agent_name` is filled on 876,325 (20.5%).

## Decision

### O1 person evidence

A natural person is identified when **both** `firstname` and `lastname` are non-blank on an HPD contact whose `type` is one of:

- `HeadOfficer`
- `IndividualOwner`
- `JointOwner`
- `Officer`
- `Shareholder`

Those five types have first+last on ≥99% of rows. `CorporateOwner` is an entity name (125,395 / 125,548 have `corporationname`; 5 have `firstname`). `Agent`, `SiteManager`, and `Lessee` are not O1 — they are management or occupancy roles, not ownership. Agent names are also **not** used as portfolio person-links (one managing agent would collapse unrelated buildings).

A NY DOS `chairman_name` that the **rules** classifier assigns as `individual` is also O1. Entity-classified chairman strings (service companies) are not.

### Residual O3

Assignment order:

| rule_id | Tier | Test |
|---|---|---|
| `T010_hpd_person` | O1 | HPD person type with first+last |
| `T020_dos_chairman` | O1 | DOS chairman classifies as `individual` |
| `T030_cluster_o1` | O2 | No own person, but another member of the cluster is O1 |
| `T040_entity_chain` | O4 | No person; linked records include another entity name (HPD `CorporateOwner` or a DOS process name that classifies as llc/corp/partnership and differs from the owner) |
| `T050_no_person` | O3 | Residual: no identifiable person |

`agent_address_only` (every stored address is denylisted, C/O, or empty) is **evidence**, not a gate. O3 is “we cannot name a person,” including unique private-looking addresses.

O4 beats O3 when an entity-only chain exists, even if the address is also an agent address.

### Non-entities

Trusts, individuals, estates, co-ops, HDFCs, public, nonprofit, lenders, and unknowns do not receive a tier. Metrics are among entity-owned private residential lots only.

## Consequences

1–2 family LLCs with no HPD registration and no DOS CEO name will usually be O3. That is a coverage limit, not a missing join. Changing O1 contact types or making agent-address a required O3 conjunct is a new ADR, not a silent retune.
