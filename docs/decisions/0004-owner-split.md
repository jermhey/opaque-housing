# ADR 0004: Split owner names on slash only

Status: accepted (2026-09-16); amended (2026-09-16, estate suffixes)

## Context

The brief says to split multiple owners. PLUTO `ownername` uses both `&` (usually a couple) and `/` (often two distinct parties).

## Decision

- Normalize, then split on `/` only.
- `JOHN SMITH & MARY` remains one `individual` record.
- Classification uses the first slash-separated party as the primary name.
- **Amendment:** if a *later* slash part is exactly `LWT`, `EST`, `EST OF`, `ESTATE`, `ESTATE OF`, or `DEF`, the record is `estate` (`R051_estate_suffix`). Verified on the 26v2 extract: `/LWT` is last-will (11 names); `/ESTATE` and `/EST OF` are probate (3 names); `/DEF` appears once, paired with `/LWT`. `DEFT` (defendant) does **not** match.

## Consequences

Joint tenancy spelled with a slash is under-split. Two unrelated owners joined by `&` stay one record. `owner_key` stays the hash of the first party; only the class changes when a later part is an estate suffix. Trust dates written with slashes (`U/A/D 2/3/2022`) are not estate suffixes.
