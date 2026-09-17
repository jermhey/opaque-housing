# ADR 0004: Split owner names on slash only

Status: accepted (2026-09-16)

## Context

The brief says to split multiple owners. PLUTO `ownername` uses both `&` (usually a couple) and `/` (often two distinct parties).

## Decision

- Normalize, then split on `/` only.
- `JOHN SMITH & MARY` remains one `individual` record.
- Classification uses the first slash-separated party as the primary name.

## Consequences

Joint tenancy spelled with a slash is under-split. Two unrelated owners joined by `&` stay one record. Revisit if gold-set errors concentrate here.
