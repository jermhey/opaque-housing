# ADR 0002: PLUTO cannot supply mailing addresses or condo unit owners

Status: accepted (2026-09-16)

## Context

The brief's canonical `parcels_snapshot` has `owner_mailing_address_raw` and `building_type=condo_unit`. NYC M0 uses PLUTO.

## Decision

- `owner_mailing_address_raw` is **null** on the PLUTO adapter. The lot `address` field is not a mailing address and will not be silently reused.
- PLUTO condo rows are mapped to `condo_unit` at the **billing-lot / complex** grain. Unit-level owners and the billing↔unit crosswalk wait for ACRIS Legals + DCP PAD in M2.
- `geo_neighborhood` is filled only when the official tract→NTA equivalency file is supplied. PLUTO itself has no NTA column.
- `geo_tract` is the 2020 census GEOID, constructed from official NTA `countyfips` + PLUTO `bct2020`.

## Consequences

Current-stock condo shares from PLUTO describe who is on the billing lot, not who owns each unit. The site and methodology must say so. Mailing-address clustering (M3) cannot use PLUTO alone.
