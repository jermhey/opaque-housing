# Project Brief: Opaque Residential Ownership Investigation

> **How to use this in Cursor**
> 1. Save this file in the repo as `docs/PROJECT_BRIEF.md`.
> 2. Copy Section 12 ("Working Agreements") into `.cursor/rules/project.mdc` so the rules apply to every agent session.
> 3. Paste Section 13 ("Kickoff") into Agent chat to start.
>
> Placeholder repo name: `opaque-housing`.

---

## 1. Role and Objective

You are a senior data/platform engineer helping me build a **public, deployed, reproducible investigation** of this question:

> **How much residential housing is held behind opaque ownership (LLCs, corporations, trusts, shell chains), and is that share growing?**

This is an investigation, not a SaaS product. Still, it must be engineered like production software:
- tested and typed;
- CI/CD;
- scheduled data refreshes;
- a deployed public site;
- an evaluation harness for every classification step.

Architecture requirement: start with one metro, and design every layer so a second and third metro can be added with a new adapter only.

## 2. Research Questions

**Primary**
1. **Stock.** What share of private residential units, and separately parcels, is owned by entities vs. individuals vs. trusts? Break down by geography and building type.
2. **Flow.** What share of arm's-length residential purchases each year have an entity buyer? How has that changed over time?

**Secondary**
3. **Opacity depth.** Of entity-owned housing, how much has *no identifiable natural person* anywhere in public records?
4. **Concentration.** How concentrated is entity ownership once related entities are clustered into portfolios?
5. **Comparison (later milestones).** How do metros compare, using identical definitions?

## 3. Definitions (get these right before writing metric code)

### 3.1 Owner classes (mutually exclusive, one per owner record)

| Class | Examples | Notes |
|---|---|---|
| `individual` | JOHN SMITH; SMITH JOHN & MARY | Includes "ET AL", "JTWROS" |
| `trust` | SMITH FAMILY TRUST; JOHN SMITH TRUSTEE | Kept separate from entities. Most are ordinary revocable living trusts used for probate avoidance, not concealment. |
| `estate` | ESTATE OF JOHN SMITH | |
| `llc` | 123 MAIN ST LLC | Normalize all LLC spellings |
| `corp` | ABC REALTY CORP; ABC INC | |
| `partnership` | ABC ASSOCIATES LP; LLP | |
| `coop_corp` | Co-op housing corporations | **NYC-specific trap:** every co-op building is corporate-owned by design. Never count these as opaque. Identify them by building class, not name. |
| `hdfc` | HOUSING DEVELOPMENT FUND CORP | Affordable co-ops; separate class |
| `public` | CITY OF NEW YORK; NYCHA; federal agencies | Excluded from the private denominator; reported separately |
| `nonprofit_religious` | Churches, universities, nonprofits | Excluded from the private denominator |
| `lender_reo` | Banks, FNMA/FHLMC, servicers | Report separately |
| `unknown` | Unclassifiable or blank | Always reported. Never silently dropped. |

### 3.2 Headline groupings

- **Entity-owned** = `llc` + `corp` + `partnership`.
- `trust` is reported as its own series and **never** folded into the headline.
- Publish a sensitivity table that shows the headline with and without trusts.

### 3.3 Opacity tiers (entity-owned records only)

| Tier | Meaning | Test |
|---|---|---|
| O1 | Identifiable | A natural person is named in a linked public record (e.g., NYC HPD registration head officer/owner, or state filing) |
| O2 | Semi-opaque | No natural person found, but the entity belongs to a portfolio cluster whose parent is identifiable |
| O3 | Opaque | No natural person found, and the only addresses are registered-agent, law-firm, or c/o addresses |
| O4 | Layered | The entity's linked records point only to other entities (entity-owns-entity chain) |

Tier rules must be explicit, versioned, and unit-tested. Record which evidence produced each tier assignment.

### 3.4 Denominators and building types

- Always compute both **unit-weighted** and **parcel-weighted** shares.
- Canonical building types:
  - `sfr_1_4` (1–4 family)
  - `condo_unit`
  - `small_mf` (5–19 units)
  - `large_mf` (20+ units)
  - `mixed_use_res`
  - `coop_building`
  - `other_res`
- Large multifamily has always been mostly entity-owned. The most informative series is **entity share of `sfr_1_4` + `condo_unit`**. Always break results out by building type rather than pooling.

### 3.5 Arm's-length sale (flow metric)

A transfer counts as a sale when all of these hold:
- it is a deed-type document;
- consideration is above a configurable threshold (start at $10,000);
- it is not flagged as intra-family, transfer-to-own-trust, or correction/confirmatory.

The threshold and the exclusion rules are config values. Run a sensitivity analysis on each.

## 4. Data Sources

**Rule: verify before use.** Before writing any adapter, download a sample and record the following in `docs/data_sources.md`:
- the real schema;
- row count and coverage by year;
- the dataset ID/URL and retrieval date;
- license/terms.

Do not assume field names or codes from memory. Lookup tables (document types, building classes, land-use codes) must come from the official code datasets, not be hardcoded from recall.

### 4.1 Metro 1: New York City (start here)

NYC is first because it publishes owner names and full deed party records in bulk for free.

- **MapPLUTO / PLUTO** (NYC Open Data / DCP)
  - Current snapshot per tax lot: owner name, owner type, residential units, building class, land use, BBL, census tract.
  - Archived annual PLUTO versions can provide historical snapshots. Check availability.
  - Check condo handling: PLUTO uses condo billing lots, while deeds reference unit lots. A billing-lot ↔ unit-lot mapping is required.
- **ACRIS Real Property datasets** (NYC Open Data):
  - `Master`: document ID, doc type, dates, amount;
  - `Legals`: document → borough/block/lot;
  - `Parties`: document grantor/grantee name and address;
  - the ACRIS **Document Control Codes** table for doc-type semantics.
  - Measure party-data coverage by borough and year, then set the analysis window from the data.
- **HPD Multiple Dwelling Registrations + Registration Contacts** (NYC Open Data)
  - Buildings with 3+ units register owners, head officers, and managing agents.
  - Primary source for O1 opacity evidence and portfolio linking.
- **NY Department of State corporation data** (data.ny.gov)
  - Entity name, DOS ID, formation date, jurisdiction, entity type, process/registered-agent address.
  - Check whether inactive/dissolved entities are included.
  - Used for: entity-formed-shortly-before-purchase signal; shared process addresses; foreign (out-of-state) LLC flag.
- **Geography**: 2020 census tracts and NYC Neighborhood Tabulation Areas (NTAs) for aggregation.

### 4.2 Metro 2 (adapter test): Philadelphia

- Verify: OPA property assessments (owner fields, mailing address, category code) and Real Estate Transfer Tax records (grantors, grantees, doc type, consideration, date).
- Verify: whether Pennsylvania business-entity data is available in bulk. If not, the O-tier logic must degrade gracefully per metro.

### 4.3 Explicitly out of scope for now: Los Angeles County

- California counties generally do not publish owner names in open bulk assessor data, and there is no open statewide California ownership layer.
- Do not build an LA adapter unless I provide a licensed data source.
- If LA is ever added: California's heavy use of revocable living trusts makes the trust/entity separation in 3.2 even more important.

### 4.4 Optional enrichment (Milestone 4+)

- Cross-reference entity names against **OpenSanctions** and **ICIJ Offshore Leaks**. I have prior adapter code for both and will point you to it.
- Fuzzy name matches are **internal review flags only**. They are never published or used in metrics without manual confirmation.

## 5. Architecture

### 5.1 Stack (defaults; propose changes with reasons)

| Area | Default |
|---|---|
| Language & packaging | Python 3.11+, `uv` |
| Lint / format | `ruff` |
| Type checking | `pyright` (or `mypy`) |
| Tests | `pytest` |
| Storage & compute | DuckDB + Parquet, local-first |
| DataFrames | Polars, where SQL is awkward |
| CLI | `typer`: `oh ingest`, `oh build`, `oh eval`, `oh publish`, `oh label` |
| LLM | Anthropic API. Model ID via the `ANTHROPIC_MODEL` env var; never hardcoded. |
| Site | Evidence.dev (SQL-first, reads DuckDB/Parquet) as the default. Observable Framework is the fallback; justify the switch if you make it. |
| Hosting | Cloudflare Pages or Vercel for the site. Object storage (R2/S3) for published Parquet aggregates. |
| Packaging | `Dockerfile` for the pipeline; `Makefile` or `justfile` for common tasks |

### 5.2 Repo layout

```
opaque-housing/
├── src/opaque_housing/
│   ├── adapters/            # ALL source-specific I/O lives here
│   │   ├── base.py          # MetroAdapter protocol
│   │   ├── nyc/             # pluto.py, acris.py, hpd.py, nys_dos.py
│   │   └── phl/
│   ├── schema.py            # canonical tables (pydantic/pandera or DuckDB DDL)
│   ├── normalize/           # name + address normalization (pure functions)
│   ├── classify/
│   │   ├── rules.py         # ordered rules, each with a rule_id
│   │   ├── llm.py           # fallback classifier, cached, versioned prompt
│   │   └── pipeline.py
│   ├── resolve/             # portfolio clustering (union-find)
│   ├── opacity/             # O-tier assignment
│   ├── metrics/             # stock, flow, concentration, corrected estimates
│   ├── quality/             # data-quality checks, run manifest
│   └── cli.py
├── eval/
│   ├── gold/                # hand-labeled owner names (dev/test split)
│   └── reports/
├── site/                    # Evidence/Observable project
├── tests/
│   └── fixtures/            # small committed sample Parquet per adapter
├── analysis/                # notebooks allowed here; never imported by src
├── docs/
│   ├── PROJECT_BRIEF.md
│   ├── data_sources.md
│   ├── methodology.md
│   └── decisions/           # short ADRs, one per non-obvious choice
├── .github/workflows/       # ci.yml, refresh.yml, deploy.yml
├── Dockerfile
├── .env.example
└── README.md                # includes an "Honest limits" section
```

### 5.3 Canonical schema (adapters output exactly this)

- **`parcels_snapshot`**
  - `metro_id`, `parcel_id`, `snapshot_date`
  - `geo_tract`, `geo_neighborhood`
  - `building_type` (canonical), `res_units`
  - `owner_name_raw`, `owner_mailing_address_raw`
  - `source_dataset`, `source_version`
- **`transfers`**
  - `metro_id`, `doc_id`, `recorded_date`, `doc_date`
  - `doc_type_raw`, `doc_type_canonical` (`sale_deed` | `nonsale_deed` | `other`)
  - `consideration`, `parcel_ids` (list)
  - `source_dataset`, `source_version`
- **`transfer_parties`**
  - `metro_id`, `doc_id`, `role` (`grantor` | `grantee`)
  - `name_raw`, `address_raw`
- **`owners`** (derived)
  - `owner_key` (hash of normalized name), `name_normalized`
  - `owner_class`, `class_source` (`rule` | `llm` | `manual`), `rule_id`
  - `model_id`, `prompt_version`, `confidence`
- **`entity_records`** (derived, from state filings)
  - `entity_id`, `name_normalized`, `formation_date`, `jurisdiction`
  - `entity_type`, `process_address_normalized`
- **`owner_links`**: `owner_key_a`, `owner_key_b`, `link_type`, `evidence_ref`
- **`owner_clusters`**: `cluster_id`, `owner_key`
- **`opacity`**: `owner_key`, `tier`, `evidence` (JSON), `rules_version`

Adapters handle metro quirks (condo lot mapping, doc codes, building classes). Everything downstream is metro-agnostic.

## 6. Pipeline Stages

1. **Ingest.** Download raw data to `data/raw/<metro>/<dataset>/<retrieval_date>/`, keeping it immutable. Write the raw-to-canonical mapping per adapter.
2. **Normalize.**
   - Names: uppercase, strip punctuation, collapse whitespace.
   - Canonicalize suffixes: `L.L.C.`, `L L C`, `LIMITED LIABILITY CO` → `LLC`; `TR`, `TRST`, `TTEE`, `TRUSTEE` → trust tokens.
   - Split multiple owners.
   - Addresses: parse to comparable form (e.g., `usaddress`) and flag `C/O` lines.
3. **Classify.**
   - Run ordered deterministic rules first, each with a `rule_id` and unit tests. Rules resolve conflicts (e.g., "JOHN SMITH TRUSTEE OF SMITH TRUST" → `trust`).
   - Identify co-ops and HDFCs by building attributes as well as name.
   - Send **only** names that no rule matches, or that conflicting rules match, to the LLM.
4. **LLM fallback.**
   - Batched structured output: enum class plus a one-line rationale; temperature 0.
   - Send names only, never addresses or other personal context.
   - Cache in DuckDB keyed by `(owner_key, prompt_version, model_id)`.
   - Log token usage and cost per run. Enforce a configurable cost cap that aborts the run.
5. **Resolve portfolios.** Union-find over links:
   - identical normalized mailing address;
   - identical state-filing process address;
   - shared HPD head officer / owner name;
   - exact name match across roles.

   Maintain a **high-degree address denylist** (registered-agent services, large law firms, management companies above a degree threshold) so the graph does not collapse into one giant component. Report component-size distribution and flag any component above a threshold for manual review.
6. **Assign opacity tiers** per Section 3.3, storing the evidence behind each assignment.
7. **Compute metrics.**
   - **Stock:** current snapshot from PLUTO.
   - **Historical stock:** reconstruct owner-at-date from the latest sale deed on or before each date.
   - **Flow:** by year × geography × building type.
   - **Concentration:** top-N portfolio share; HHI by neighborhood.
   - Every metric is available both parcel-weighted and unit-weighted.
8. **Quality gate.**
   - Write a run manifest: row counts in/out for every stage and filter, null rates, source versions, timestamps.
   - Fail the run on configurable anomalies (e.g., row count changes >X% vs. the last run).

## 7. Evaluation and Validation (non-negotiable)

- **Gold set.** Build ~600 owner names, stratified by rule outcome, borough, and building type.
  - Build a tiny `oh label` CLI so I can label them quickly.
  - Split 50/50 dev/test. The test split is never used for tuning rules or prompts.
- **Classifier report.** Per-class precision/recall and a confusion matrix, reported separately for rules-only and rules+LLM.
  - CI fails if test-set macro-F1 drops below the stored baseline.
- **Misclassification-corrected shares.** Use the confusion matrix to adjust headline shares (Rogan–Gladen-style correction or equivalent). Report raw and corrected side by side, with bootstrap intervals.
- **Internal consistency check.** Reconstructed current owner class from deeds vs. PLUTO's current owner name. Report the agreement rate by building type and investigate disagreements.
- **Portfolio clustering review.** Manually review the 20 largest clusters; record false merges and splits in `eval/reports/`.
- **External sanity check.** Compare direction and rough magnitude against published investor-purchase research. Cite sources in `methodology.md`. Do not tune the analysis to match them.

## 8. Known Pitfalls (write a test or check for each)

- **Co-op buildings** appear corporate-owned. Co-op share sales are not real-property deeds.
- **Condo billing lots vs. unit lots** cause double counting or missed units.
- **LLC membership-interest sales generate no deed.** Flow metrics *undercount* entity turnover. State this limitation on the site.
- **Multi-parcel deeds**: consideration covers the bundle, so never compute per-parcel price naively.
- **Transfers to one's own trust or LLC** ($0 or nominal consideration) are not market purchases.
- **Truncated owner names** in assessor fields; `C/O` lines holding the real party; `ET AL`.
- **Amended, corrected, or duplicate recordings** of the same transaction.
- **Land-use/building-class codes that change over time** for the same parcel.
- **Public-entity and nonprofit owners** must leave the private denominator *before* shares are computed.
- **Giant components** in portfolio clustering (see the denylist in Section 6).
- **Survivorship in state entity data** if dissolved entities are missing, which biases the formation-date analysis.

## 9. Deployment and Operations

- **`ci.yml`** (every push): ruff, pyright, pytest on committed fixtures, gold-set eval regression check.
- **`refresh.yml`** (scheduled, e.g., monthly):
  1. Check source-dataset update timestamps.
  2. Run the pipeline incrementally.
  3. Run the quality gate.
  4. Publish aggregate Parquet/CSV to object storage.
  5. Trigger the site build.

  First measure full dataset sizes. If they exceed GitHub-hosted runner limits, propose an alternative (self-hosted runner, small cloud VM, or incremental-only refresh) in an ADR.
- **`deploy.yml`**: build and deploy the site.
- **Site pages:**
  - headline findings;
  - interactive neighborhood map/table;
  - trends over time;
  - building-type breakdown;
  - **methodology**;
  - **data dictionary**;
  - **limitations**;
  - **data freshness** (from the run manifest);
  - downloadable aggregates.
- **Reproducibility:** `docker run ... oh build --metro nyc` reproduces published aggregates from raw data.

## 10. Ethics and Privacy

- Publish **aggregates only** at tract/neighborhood level or coarser. Suppress cells below a minimum unit count (configurable; start at 10).
- Never publish individuals' names or addresses. The committed gold set stores normalized names only for entities; individuals' names in the gold set stay out of the public repo (gitignored, stored locally).
- Entity-level or portfolio-level public pages are **deferred** and need my explicit sign-off plus a review process.
- Respect source terms of use and rate limits. Identify the client with a User-Agent.
- Send names only to the LLM. Document this in `methodology.md`.

## 11. Milestones (stop after each and report)

**M0: Scaffold and source verification**
- Repo layout, CI green, `.env.example`, Dockerfile.
- `docs/data_sources.md` completed for all NYC sources (schemas, sizes, coverage by year, terms).
- `MetroAdapter` protocol and canonical schema defined; NYC PLUTO adapter producing `parcels_snapshot` on a fixture.
- **Done when:** `make test` passes, and the data-source doc has real verified schemas.

**M1: Current-stock baseline (rules only)**
- Normalization + rules classifier + co-op/HDFC handling.
- `oh label` CLI; gold set labeled (I label; you build the tool).
- Stock shares by borough/NTA × building type, both weightings.
- **Done when:** eval report exists, and headline numbers are shown raw and corrected with intervals.

**M2: Flow and history**
- ACRIS adapter (Master/Legals/Parties/doc codes), condo lot mapping, sale-deed filter.
- Entity-buyer share by year; reconstructed historical stock; consistency check vs. PLUTO.
- **Done when:** trend series exists with a sensitivity table (threshold and exclusion rules) and a documented coverage window.

**M3: LLM fallback and opacity**
- LLM classifier with cache, cost cap, prompt versioning; eval shows the lift over rules-only on the test split.
- HPD + NY DOS adapters; portfolio clustering with denylist; O-tier assignment.
- **Done when:** opacity-tier shares are published internally, and the top-20 cluster review is logged.

**M4: Ship it**
- Site deployed with all pages in Section 9; scheduled refresh working end-to-end.
- Optional sanctions/leaks enrichment (internal flags only).
- **Done when:** a public URL exists, refresh has run successfully at least once unattended, and the README has honest limits.

**M5: Second metro**
- Philadelphia adapter using only adapter-layer code. Any change needed downstream is a design flaw: log it and fix the abstraction.
- **Done when:** a comparative NYC vs. PHL page exists with identical definitions and per-metro caveats.

## 12. Working Agreements (copy into `.cursor/rules/project.mdc`)

- **Inspect data before coding against it.** Never invent field names, codes, or dataset IDs. If you can't verify something, say so and ask.
- **Keep code pure where possible.** Classification, opacity, and metric logic are pure functions with no I/O. All network and file access lives in adapters and the CLI.
- **Test every rule.** Every classification rule has a `rule_id` and at least one positive and one negative test.
- **Never drop rows silently.** Every filter logs before/after counts to the run manifest.
- **Surface definitional ambiguity as a question to me.** Record resolved decisions as ADRs in `docs/decisions/`.
- **Commit small** with descriptive messages. Repo history is part of the deliverable.
- **Keep notebooks in `analysis/` only.** Nothing in `src/` imports them.
- **Handle secrets via `.env`.** Never commit keys or raw personal data.
- **Prefer boring, well-documented tools.** Justify any new dependency in one line in the PR/commit description.
- **Report at the end of each milestone:**
  - what was built;
  - what was verified vs. assumed;
  - open questions;
  - the numbers produced so far, with caveats.
- **Do not start the next milestone until I confirm.**

## 13. Kickoff (paste this into Cursor Agent)

> Read `docs/PROJECT_BRIEF.md` in full. We are starting **Milestone 0** only.
>
> 1. First, propose the concrete file list and tooling versions for the scaffold. Wait for my OK.
> 2. Then build the scaffold and CI.
> 3. Then verify each NYC data source in Section 4.1: pull small samples, record real schemas, sizes, year coverage, and terms in `docs/data_sources.md`. Flag anything in the brief that turns out to be wrong.
> 4. Implement the `MetroAdapter` protocol, the canonical schema, and the PLUTO adapter against a committed fixture, with tests.
>
> Stop when M0's "done when" criteria are met, and give me the milestone report described in Section 12.
