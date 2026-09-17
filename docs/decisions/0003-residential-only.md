# ADR 0003: Residential lots only in `parcels_snapshot`

Status: accepted (2026-09-16)

## Context

M0 asked whether non-residential PLUTO lots should stay in the canonical snapshot. The research question is about residential housing.

## Decision

Emit only residential lots. Filter `pluto_residential_only` logs `rows_in` / `rows_out` on the adapter (`FilterCount`). A lot is residential if any of these official tests hold:

- `unitsres >= 1`
- DCP land use 1–4
- building class is an official coop, residential condo (including billing-lot rollups), 1–4 family, or S* mixed-use class

Vacant land, city yards, retail, and other non-res lots leave the snapshot here — not later, silently, in metrics.

`A8` (bungalow colony, cooperatively owned land) stays a `coop_building` and is in-universe residential.

## Consequences

Private-denominator exclusions (public, nonprofit) still happen at the owner-class stage, after this lot filter. A public agency that owns a residential building remains in `parcels_snapshot` with its owner name.
