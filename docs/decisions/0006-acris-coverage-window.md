# ADR 0006: ACRIS coverage window and extract quirks

Status: accepted (2026-09-17)

## Context

The brief says to measure party coverage by borough and year, then set the analysis window from the data. Live probes on 2026-09-17 (`bnx9-e6tj`, `636b-3b5g`, `8h5j-fqxa`).

## Decision

**Primary window: recorded years 2003–2025.** 2026 is ingested but dropped from year-over-year tables because the extract ends mid-year (max `recorded_datetime` on 2026-09-16 was 2026-08-31).

Reasons, all measured:

1. **Consideration appears in 2003.** `DEED` rows with `document_amt >= 10000`: 0–7 per year from 1966 through 2002; 31,695 of 51,337 in 2003; 58,841 of 92,033 in 2004. The brief’s $10k filter cannot be applied before 2003.
2. **`document_id` format changes in 2003.** Earlier IDs are reel-style (`BK_6630026700143`, `FT_1700008653870`). From 2003 they are `YYYYMMDD` + sequence (`2003010900487001`). Party/legal extracts for the window use `document_id >= '2003010100000000' and document_id < '2027010100000000'` (ASCII-safe: `BK_`/`FT_` fall outside).
3. **Party names are present in the window.** 40-document samples of `DEED` in 1985, 1995, 2005, 2015, 2020, and 2024 each had 40/40 named `party_type = 2` rows. The window is *not* set by missing names; it is set by usable consideration and a stable id scheme.

## Extract rules (always on)

- **Snapshot dedup.** Master/Legals/Parties repeat `document_id` across `good_through_date` values. Keep the latest `good_through_date` per grain (`document_id` on Master; `document_id` + boro/block/lot on Legals; `document_id` + `party_type` + `name` + `address_1` on Parties). 2024 `DEED` raw count 52,450 vs distinct `document_id` 52,149.
- **Property borough is Legals `borough`, not Master `recorded_borough`.** 2024 `DEED` `recorded_borough` is 48,764 in 1 and only hundreds in 2–4. That is the recording office, not the tax lot.
- **Year is `recorded_datetime`, not `document_date`.** `document_date` has garbage minima (`0001-04-03`).
- **Multi-parcel deeds are one purchase.** Consideration is for the bundle. Unit weight is the sum of matched residential units; a PAD-mapped condo unit counts as 1 unit, not the billing-lot complex size.

## Consequences

Pre-2003 deeds can still be used in a later “names-only / no amount filter” history series. They are out of the published M2 window. Any change to 2003–2025 requires a new ADR plus a re-measured amount-by-year table.
