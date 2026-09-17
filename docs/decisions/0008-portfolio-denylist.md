# ADR 0008: Portfolio links and the high-degree denylist

Status: accepted (2026-09-17)

## Context

The brief clusters entity owners with union-find over shared mailing / process addresses, shared HPD officer names, and exact name matches. A high-degree address denylist is required so registered-agent shops do not collapse the graph. NY DOS process-name frequencies were read live from `n9v6-gdp6` on 2026-09-17 (top row: `THE LIMITED LIABILITY COMPANY` = 93,064). HPD business-address frequencies were read from `feu5-w2e2` (several buildings exceed 1,000 contact rows).

PLUTO has no owner mailing address (ADR 0002). Mailing-like addresses for current stock come from HPD contact business addresses and DOS process / registered-agent addresses.

## Decision

### Link types (exact match only; no fuzzy)

| `link_type` | Nodes | Key |
|---|---|---|
| `hpd_person` | Two entity `owner_key`s | Normalized `FIRST LAST` on an O1 contact type (ADR 0007) at their latest HPD registration |
| `hpd_address` | Two entity `owner_key`s | Normalized HPD business address, not denylisted |
| `dos_process_address` | Two entity `owner_key`s | Normalized DOS process address, not denylisted |
| `exact_name` | Parcel owner ↔ HPD `CorporateOwner` (not Agent / SiteManager / Lessee) | Same `owner_key` after `normalize_name` |

`Agent` / `SiteManager` / `Lessee` never generate `hpd_person` links **or** `exact_name` hubs. A managing agent’s corporation name would otherwise star-link every client building into one component.

Latest HPD registration per BBL = max `lastregistrationdate`, then max `registrationid`. Expired `registrationenddate` is kept (annual cycle); it is recorded on the evidence, not used as a drop.

### Denylist

An address is denied when any of these hold:

1. It is empty after normalize.
2. Distinct entity `owner_key`s sharing it are **≥ 20** (`ADDRESS_DEGREE_THRESHOLD`).
3. The process / registered-agent **name** on that record is in the committed seed list (`nys_dos_agent_names.csv`), which is the 2026-09-17 top DOS process names and top registered-agent names (plus the empty-name bucket). Names are compared after `normalize_name`.

A leading `C/O` or `CARE OF` flags the address (`is_care_of`) but does not by itself deny it unless the remainder is a seed agent or the degree test fires.

Denied addresses and seed agent names produce **no** cluster link. They still appear on opacity evidence (`agent_address_only`).

Person names are **not** degree-denylisted. A HeadOfficer on 200 buildings is treated as a real portfolio; components above 200 entity parcels are flagged for the top-20 review rather than silently split.

### Clustering grain

Only **entity** `owner_key`s are nodes. Individuals, trusts, and other non-entity parcel owners are not intermediate hubs — including them produced a 28k-owner component via shared officers and sub-threshold addresses.

Cluster edges are `hpd_person` and `exact_name` only. Shared addresses still set `agent_address_only` and the denied-address table; they are not union-find edges. Mixing address edges with officer edges among entities alone still produced a 6k+ component.

Extra nodes (HPD `CorporateOwner` names that classify as entities) may join so entity-owns-entity chains exist. Headline shares and the top-20 review count **PLUTO entity parcel owners** only. Components with ≥200 entity owners are flagged `large_component`.

## Consequences

Threshold 20 is a round number chosen after seeing HPD addresses with thousands of contact rows and DOS agents with tens of thousands of entities. Raising or lowering it is a new ADR. Seed agent names are frozen to the 2026-09-17 probe; refreshing the list is a documented extract, not an ad-hoc edit.
