# ADR 0012: Cook / Miami-Dade metro IDs and compare registry

Status: accepted (2026-09-18)

## Context

ADR 0010 added Philadelphia as a second metro with hardcoded `nyc` / `phl` branches in the CLI, `KNOWN_METROS`, and `mix_adjust()`. A third metro would copy that ladder. The next metros are **counties**, not city limits: Cook County and Miami-Dade County. Los Angeles County has no free owner-name or sales file (Assessor Data Sales is paid) and is deferred.

## Decision

### Metro IDs

| `metro_id` | Display name | Geography |
|---|---|---|
| `nyc` | New York City | unchanged |
| `phl` | Philadelphia | unchanged (city = county) |
| `cook` | Cook County | full county file, including suburbs |
| `dade` | Miami-Dade County | full county folio file, including municipalities other than the City of Miami |

Do not title charts “Chicago” or “Miami.”

### Los Angeles

Deferred. The free Hub roll has use codes and units but no owner names and no sales series. No `lax` adapter until an official Local Roll / Sales List is purchased and kept off git.

### Registry

`opaque_housing.metros` is the list of known IDs, display names, coverage windows, and neighborhood grain. The CLI, app store, and GitHub sync read that list. `mix_adjust(reference, other, *, reference_id, other_id)` is pairwise. NYC remains the default reference mix. `/v1/compare/mix` takes `other=phl|cook|dade` (default `phl`).

### What stays NYC-only

Gold correction, O-tiers, ACRIS/HPD/DOS, and PAD condo mapping.

## Consequences

A new metro is still a new adapter emitting `ParcelSnapshot` / `Transfer`. Compare copy must name the county. Cook stock+sales were timed 2026-09-18 (~14 min) and are on `refresh.yml`. Miami-Dade GIS was timed (~15 min) but stays laptop-only: no local SDF, and the MapServer silently caps pages.
