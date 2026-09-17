# Methodology

Definitions live in [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) §3. This file records how those definitions are implemented, plus sources for external sanity checks.

Milestone 0 has no metric implementation yet. Classifier rules, sale filters, and opacity tiers will be documented here as they land, with a version for each rule set.

## Names-only LLM constraint

When the LLM fallback lands (M3), prompts will receive owner **names only**. Addresses and other personal context are not sent. Model ID comes from `ANTHROPIC_MODEL`.

## Building-type map (NYC, M0)

Canonical types are assigned from official DOF building-class codes (plus DCP's PLUTO-only condo rollup codes) and `unitsres` / `landuse`. Co-ops are those official classes whose published label is a cooperative (`C6`, `D4`, `A8`, …), never a name match. See `src/opaque_housing/adapters/nyc/building_type.py` and `docs/data_sources.md`.

`parcels_snapshot` is **residential lots only** (ADR 0003). The filter records before/after counts (`pluto_residential_only`).

PLUTO condo rows are billing-lot / complex grain, not unit owners (ADR 0002). Owner mailing addresses are not taken from PLUTO; clustering uses ACRIS/HPD later.

## External sanity checks

Not started. Citations will be added here in M1+; we will not tune results to match them.

## What will be documented here

- Owner-class rule list (`rule_id`, precedence, examples)
- Building-type mapping from official code tables (never from memory)
- Arm's-length sale filter and sensitivity parameters
- Opacity-tier tests and evidence fields
- LLM prompt version and the "names only" constraint
- Confusion-matrix correction method
- Citations for published investor-purchase research (comparison only; we do not tune to match)
