# Data sources

Retrieval date for every probe below: **2026-09-16**. Client User-Agent: `opaque-housing/0.1 (residential-ownership-research)`.

Nothing in this file is from memory. Dataset IDs, field names, row counts, and year spans were read from the live Socrata APIs (`/api/views/{id}.json` and `/resource/{id}.json`) or from the cited official HTML/PDF. Probe dumps (not committed) live under `analysis/source_probe/`.

## Terms

- **NYC Open Data.** [Terms of Use](https://data.cityofnewyork.us/stories/s/Terms-of-Use/k9k7-3cje/). Local Law 11 of 2012: public datasets are available without a registration or license requirement. The City disclaims completeness, accuracy, and fitness for a particular purpose. DoITT may require republication to identify source, version, and modifications. We identify the client with a User-Agent and will cite dataset ID + version + retrieval date on published aggregates.
- **DCP PLUTO / MapPLUTO / PAD.** DCP states the files are informational only and carries the same no-warranty language ([PLUTO 26v2 readme](https://s-media.nyc.gov/agencies/dcp/assets/files/pdf/data-tools/bytes/pluto_readme.pdf)).
- **OPEN NY (data.ny.gov).** [OPEN-NY Terms of Use](https://data.ny.gov/en/dataset/OPEN-NY-Terms-Of-Use/77gx-ii52). Lawful reuse, including commercial use, is permitted; state disclaimers still apply.

## What the brief got wrong or incomplete

| Brief assumption | What the live sources show |
|---|---|
| PLUTO has an owner mailing address | **It does not.** `address` is the *tax-lot* address. Owner mailing is not a PLUTO field. Transfer-party addresses are in ACRIS Parties (`address_1`, `city`, `state`, `zip`). HPD contacts have a business address. |
| PLUTO current snapshot is version 26v1 | The live `64uk-42ks` description and `version` column are **26v2** (DCP readme dated August 2026). |
| MapPLUTO is a drop-in attribute table | `f888-ni5f` returns **403** on the SODA resource API (geometry/export dataset). Use tabular PLUTO `64uk-42ks` for attributes. |
| PLUTO can support `condo_unit` ownership | PLUTO stores **one row per condo complex (billing lot)**, not per unit. `OwnerName` on those rows is the billing-lot / association name. Unit lots appear in ACRIS Legals (`lot`, optional `unit`) and in DCP PAD (`billboro` / `billblock` / `billlot`). |
| PLUTO has NTA | **No `nta2020` column** on `64uk-42ks`. Join `bct2020` → `boroct2020` on the official equivalency table `hm78-6dwm`. |
| `landuse` is a 2-character zero-padded code | Socrata types it as a **number** (`1`…`11`). 2,912 lots have a null land use. |
| NY DOS bulk data includes inactive/dissolved entities | `n9v6-gdp6` is titled **Active Corporations** (4,281,406 rows). Dissolved entities are missing from that table — the survivorship bias called out in the brief is real. `ekwr-p59j` is a name-status history (A=4.31M, I=3.18M) without process addresses. |
| DOF building-class codes are a Socrata table | `nzvw-cjc2` and PAD `bc8t-ecyu` also 403 on SODA. Official codes were taken from the [DOF HTML list](https://www.nyc.gov/assets/finance/jump/hlpbldgcode.html). DCP-created condo mix classes (RC/RD/RI/RM/RX/RZ, Q0, QG) are only in the PLUTO data dictionary. |
| HPD contact types are owner / head officer / agent | Also: `SiteManager`, `Officer`, `JointOwner`, `Shareholder`, `Lessee`. |
| ACRIS doc-type field is a simple code | Document Control Codes use **`doc__type`** (double underscore). Master uses `doc_type`. Values include `DEED`, `DEED, RC`, `CONDEED`, `CORRD`, etc. |

---

## 1. Primary Land Use Tax Lot Output (PLUTO)

| | |
|---|---|
| Portal | https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-PLUTO-/64uk-42ks |
| Dataset ID | `64uk-42ks` |
| Publisher | Department of City Planning (DCP) |
| API | `https://data.cityofnewyork.us/resource/64uk-42ks.json` |
| Ingest | `oh ingest` pulls `$select=bbl,bldgclass,unitsres,ownername,version,bct2020,borocode,landuse,condono` with `$limit=1000000` (verified field names only) |
| Version (live) | **26v2** (`version` column; catalog description) |
| Rows | **858,284** |
| Columns | 108 |
| Snapshot / not a panel | Current tax-lot snapshot. Historical annual files are on [DCP MapPLUTO/PLUTO](https://www.nyc.gov/content/planning/pages/resources/datasets/mappluto-pluto-change). |
| Dictionary | https://s-media.nyc.gov/agencies/dcp/assets/files/pdf/data-tools/bytes/pluto_datadictionary.pdf |
| Readme | https://s-media.nyc.gov/agencies/dcp/assets/files/pdf/data-tools/bytes/pluto_readme.pdf |

### Verified fields used for `parcels_snapshot`

| Socrata field | Canonical target | Notes |
|---|---|---|
| `bbl` | `parcel_id` | Number; sample values look like `4087860042.00000000`. Normalize to a 10-digit string. For condos this is the **billing lot**. |
| `ownername` | `owner_name_raw` | 81-character PTS name. Public owners are sometimes DCP-normalized. |
| `address` | (lot address only) | **Not** a mailing address. Not mapped to `owner_mailing_address_raw`. |
| `ownertype` | (kept as source attribute, not a canonical field) | C 12,997; M 77; O 1,414; P 583; X 20,390; blank 822,822; **S 1** (S is not in the data dictionary — flag). Blank usually means private. |
| `bldgclass` | input to building-type map | Official DOF 2-char codes. |
| `landuse` | input to building-type map | DCP 1–11. Sample counts: 1=566,810; 2=131,460; 3=13,288; 4=56,272; null=2,912. |
| `unitsres` | `res_units` | Residential unit count; 0 if none. |
| `condono` | condo flag | Non-null on **11,046** lots. |
| `bct2020` | `geo_tract` via GEOID construction | DCP borough+tract (`4157903`). GEOID = `36` + official county FIPS + 6-digit tract. |
| `borocode` | GEOID / join | 1–5. |
| `version` | `source_version` | `26v2`. |

`OwnerType` codes from the official dictionary: C city; M mixed city/private; O other public authority / state / federal; P private; X fully tax-exempt; blank unknown (usually private).

`parcels_snapshot` keeps **residential lots only** (ADR 0003). The adapter records `pluto_residential_only` before/after counts. Non-res lots (vacant, city yards, retail without units) are not silently dropped later in metrics.

### Building-type inputs (official, not recalled)

- DOF list: https://www.nyc.gov/assets/finance/jump/hlpbldgcode.html (committed as `dof_building_classification_codes.csv`).
- DCP extra condo mix classes: PLUTO dictionary Appendix C (committed as `dcp_pluto_extra_building_classes.csv`).
- Co-op classes used by the adapter (official labels contain cooperative / co-op): `A8, C6, C8, CC, D0, D4, DC, H7, R9`.
- HDFC is **not** a building class. NY DOS has `DOMESTIC NOT-FOR-PROFIT CORPORATION (HOUSING DEVELOPMENT FUND COMPANY) (ARTICLE XI)` (3,417 active entities) — use that plus name rules in M1.

### Condo handling (required for M2)

PLUTO 26v2 readme: one record per condominium *complex*; billing lot when assigned, else lowest unit lot. ACRIS/deeds use unit lots. Billing-lot ↔ unit-lot mapping is **DCP PAD** (`billboro`, `billblock`, `billlot`), not PLUTO. PAD portal: https://www.nyc.gov/content/planning/pages/resources/datasets/pad . NYC Open Data `bc8t-ecyu` is not queryable via SODA (403).

---

## 2. MapPLUTO

| | |
|---|---|
| Portal | https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-Map-MapPLUTO-/f888-ni5f |
| Dataset ID | `f888-ni5f` |
| SODA resource | **403 Forbidden** on 2026-09-16 |
| Role | Geometry for mapping. Attributes come from PLUTO. Not used in M0. |

---

## 3. ACRIS Real Property Master

| | |
|---|---|
| Portal | https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Master/bnx9-e6tj |
| Dataset ID | `bnx9-e6tj` |
| Rows | **17,090,001** |
| Columns | 14 |

Verified columns: `document_id`, `record_type`, `crfn`, `recorded_borough`, `doc_type`, `document_date`, `document_amt`, `recorded_datetime`, `modified_date`, `reel_yr`, `reel_nbr`, `reel_pg`, `percent_trans`, `good_through_date`.

Coverage (live aggregate, 2026-09-16):

- `recorded_datetime` min **1903-10-15**, max **2026-08-31**.
- `document_date` min is garbage (`0001-04-03`); do not use min(document_date) as the window start.
- 121 distinct recorded years. Volume ≥100k documents/year from **1966 through 2026** (61 years). Sparse before that.
- Recent recorded-year counts: 2023=267,175; 2024=274,227; 2025=295,404; 2026 (partial)=203,047.

Analysis window for flow metrics: **recorded years 2003–2025** (ADR 0006). Re-measured 2026-09-17:

- `DEED` consideration is unusable before 2003 (`document_amt >= 10000` is 0–7 rows/year for 1966–2002; 31,695 of 51,337 in 2003).
- `document_id` switches from reel-style (`BK_…`, `FT_…`) to `YYYYMMDD`+sequence in 2003.
- `DEED` raw type counts (incl. snapshot dups): 3,650,964. 2024 raw 52,450 vs distinct `document_id` 52,149.
- `document_amt` on `DEED`: 2,711,941 zero; 32,487 in (0, 10000); 906,536 ≥ 10000.
- `percent_trans` on `DEED`: 0 = 2,322,457 (treated as unspecified); 100 = 1,309,673; 50 = 10,641.
- `REIT` live count: **0**. `DEEDO` 30,160; `ASTU` 2,337; `DEED, RC` 477; `DEEDP` 2.
- `recorded_borough` is the recording office, not the tax lot (2024 `DEED`: borough 1 = 48,764; 2 = 222; 3 = 1,298; 4 = 2,166). Property borough is Legals `borough`.
- Dedup grain: latest `good_through_date` per `document_id` (Master) / per lot (Legals) / per party identity (Parties).

---

## 4. ACRIS Real Property Legals

| | |
|---|---|
| Portal | https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Legals/8h5j-fqxa |
| Dataset ID | `8h5j-fqxa` |
| Rows | **22,761,783** |
| Columns | 14 |

Verified columns: `document_id`, `record_type`, `borough`, `block`, `lot`, `easement`, `partial_lot`, `air_rights`, `subterranean_rights`, `property_type`, `street_number`, `street_name`, `unit`, `good_through_date`.

Sample includes a Queens condo-style row (`lot=1031`, `unit=313`) and a Manhattan office (`property_type=OF`). Multi-parcel deeds are expected (`document_id` 1:n lots). `property_type` codes were **not** hardcoded; they need the official property-type code table before use.

---

## 5. ACRIS Real Property Parties

| | |
|---|---|
| Portal | https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Parties/636b-3b5g |
| Dataset ID | `636b-3b5g` |
| Rows | **46,614,049** |
| Columns | 11 |

Verified columns: `document_id`, `record_type`, `party_type`, `name`, `address_1`, `address_2` (often absent), `country`, `city`, `state`, `zip`, `good_through_date`.

`party_type` counts: `1`=25,414,430; `2`=21,152,796; `3`=46,823. Document Control Codes map party 1/2 by document class (for `DEED`: party1=`GRANTOR/SELLER`, party2=`GRANTEE/BUYER`). `party_type=3` is not mapped (sample names look like people; no official third role on `DEED`). Null `name`: **3,017** (very small overall).

Party-name coverage on `DEED` (40-doc samples, 2026-09-17): 1985, 1995, 2005, 2015, 2020, 2024 each had **40/40** documents with a named `party_type=2`. The published window is still 2003–2025 because consideration, not names, is the binding constraint (ADR 0006).

This is the first verified source of *party mailing addresses*.

---

## 6. ACRIS Document Control Codes

| | |
|---|---|
| Portal | https://data.cityofnewyork.us/widgets/7isb-wh4c |
| Dataset ID | `7isb-wh4c` |
| Rows | **126** (full table committed to `acris_document_control_codes.csv`) |

Verified columns: `record_type`, `doc__type`, `doc__type_description`, `class_code_description`, `party1_type`, `party2_type`.

`class_code_description = DEEDS AND OTHER CONVEYANCES` has 34 codes, including `DEED`, `DEED, RC`, `DEEDO`, `DEEDP`, `CONDEED` (confirmatory), `CORRD` (correction deed), `DEED COR`, `TODD`, `CDEC` (condo declaration), `LEAS`, `EASE`. Sale-deed vs nonsale mapping is ADR 0005. Headline `sale_deed` codes: `DEED`, `DEED, RC`, `DEEDP`, `DEEDO`, `REIT`, `ASTU`.

---

## 7. HPD Multiple Dwelling Registrations

| | |
|---|---|
| Portal | https://data.cityofnewyork.us/Housing-Development/Multiple-Dwelling-Registrations/tesw-yqqr |
| Dataset ID | `tesw-yqqr` |
| Rows | **203,887** |
| Columns | 16 |

Verified columns (re-read 2026-09-17): `registrationid`, `buildingid`, `boroid`, `boro`, `housenumber`, `lowhousenumber`, `highhousenumber`, `streetname`, `streetcode`, `zip`, `block`, `lot`, `bin`, `communityboard`, `lastregistrationdate`, `registrationenddate`.

Ingest `$select`: `registrationid,buildingid,boroid,block,lot,lastregistrationdate,registrationenddate`.

**No owner names** on this table. Join to contacts on `registrationid`. BBL = `format_bbl_parts(boroid, block, lot)`. Latest registration per BBL = max `lastregistrationdate`, then max `registrationid`.

`lastregistrationdate` span: 1993-04-01 … 2026-07-31.

HPD's own description (agency open-data page): owners must register buildings with 3+ residential units, or 1–2 family homes that are not owner/family-occupied. That is broader than "3+" alone.

---

## 8. HPD Registration Contacts

| | |
|---|---|
| Portal | https://data.cityofnewyork.us/Housing-Development/Registration-Contacts/feu5-w2e2 |
| Dataset ID | `feu5-w2e2` |
| Rows | **810,494** |
| Columns | 15 |

Verified columns (re-read 2026-09-17): `registrationcontactid`, `registrationid`, `type`, `contactdescription`, `corporationname`, `title`, `firstname`, `middleinitial`, `lastname`, `businesshousenumber`, `businessstreetname`, `businessapartment`, `businesscity`, `businessstate`, `businesszip`.

Ingest `$select` is those fields except `middleinitial`.

`type` counts: SiteManager 167,796; Agent 161,136; HeadOfficer 132,287; CorporateOwner 125,548; Officer 75,636; IndividualOwner 50,592; JointOwner 46,640; Shareholder 41,571; Lessee 9,288.

First+last fill is ≥99% on HeadOfficer / IndividualOwner / JointOwner / Officer / Shareholder. CorporateOwner is an entity name (125,395 / 125,548 have `corporationname`). O1 contact types and the agent exclusion are ADR 0007.

---

## 9. NY Department of State — Active Corporations

| | |
|---|---|
| Portal | https://data.ny.gov/Economic-Development/Active-Corporations-Beginning-1800/n9v6-gdp6 |
| Dataset ID | `n9v6-gdp6` |
| Host | data.ny.gov |
| Rows | **4,281,406** |
| Columns | 30 |
| Filing-date span | 1800-02-16 … 2026-09-15 |

Verified columns (re-read 2026-09-17): `dos_id`, `current_entity_name`, `initial_dos_filing_date`, `county`, `jurisdiction`, `entity_type`, `dos_process_name`, `dos_process_address_1`, `dos_process_address_2`, `dos_process_city`, `dos_process_state`, `dos_process_zip`, `chairman_name` (catalog label: CEO Name), `chairman_address_*`, `registered_agent_name`, `registered_agent_address_*`, `location_*`.

Ingest `$select`: identity, filing, process address, `chairman_name`, and registered-agent name/address. `dos_id` is an unpadded numeric string; full extracts use lexicographic keyset pagination (same coverage as numeric order).

Fill rates (live count, 2026-09-17): `chairman_name` 472,391 / 4,281,406 (11.0%); `registered_agent_name` 876,325 (20.5%). Top process names are registered-agent mills (`THE LIMITED LIABILITY COMPANY` 93,064; `NORTHWEST REGISTERED AGENT LLC` 49,379; …) — committed as `nys_dos_agent_names.csv` (ADR 0008).

Top `entity_type` values: domestic LLC 2,052,674; domestic business corp 1,450,181; domestic NFP 287,477; foreign LLC 172,991; foreign business corp 134,789; domestic LP 15,175; **HDFC (Article XI) 3,417**.

Inactive/dissolved entities are **not** in this extract. Formation-date-before-purchase signals will be biased toward survivors. Name match to PLUTO owners is exact `normalize_name` only.

Companion table `ekwr-p59j` (“Corporations and Other Entities: All Filings - Name Status History”): 7,493,463 rows; columns `film_num`, `date_filed`, `name_type`, `name_status`, `corp_name`. `name_status` A=4,313,513; I=3,179,950. This is name history, not a full inactive registry with process addresses.

---

## 10. Geography

### 2020 Neighborhood Tabulation Areas

| | |
|---|---|
| Portal | https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-/9nt8-h7nd |
| Dataset ID | `9nt8-h7nd` |
| Rows | **262** |

Verified attribute fields: `borocode`, `boroname`, `countyfips`, `nta2020`, `ntaname`, `ntaabbrev`, `ntatype`, `cdta2020`, `cdtaname` (+ geometry).

Official borough → county FIPS from this table (committed as `nyc_boro_county_fips.csv`):

| borocode | boroname | countyfips |
|---|---|---|
| 1 | Manhattan | 061 |
| 2 | Bronx | 005 |
| 3 | Brooklyn | 047 |
| 4 | Queens | 081 |
| 5 | Staten Island | 085 |

### 2020 Census Tracts → 2020 NTAs

| | |
|---|---|
| Portal | https://data.cityofnewyork.us/City-Government/2020-Census-Tracts-to-2020-NTAs-and-CDTAs-Equivale/hm78-6dwm |
| Dataset ID | `hm78-6dwm` |
| Rows | **2,327** |

Verified columns: `geoid`, `countyfips`, `borocode`, `boroname`, `boroct2020`, `ct2020`, `ctlabel`, `ntacode`, `ntatype`, `ntaname`, `ntaabbrev`, `cdtacode`, `cdtatype`, `cdtaname`.

Join: PLUTO.`bct2020` = equiv.`boroct2020`. Canonical `geo_tract` = `geoid`; `geo_neighborhood` = `ntacode`.

---

## Size vs. GitHub-hosted runners (preview)

Rough current extracts:

| Dataset | Rows |
|---|---|
| PLUTO | 0.86M |
| ACRIS Master | 17.1M |
| ACRIS Legals | 22.8M |
| ACRIS Parties | 46.6M |
| HPD regs + contacts | 1.0M |
| NY DOS active | 4.3M |
| Name status history | 7.5M |

Measured on 2026-09-16 (selected columns, not the full 108-column PLUTO table):

| Dataset | Rows | Bytes |
|---|---:|---:|
| PLUTO `$select` used by `oh ingest` | 858,284 | 67,098,962 |
| Tract–NTA equivalency | 2,327 | 197,482 |

A full ACRIS Parties pull is still the binding constraint. Whether a monthly GitHub-hosted runner can do a cold extract of ACRIS is **not yet measured**. An ADR is due before `refresh.yml` is written.

---

## Not yet pulled (called out so we do not pretend)

- Official ACRIS `property_type` code list (not used; lot join is boro/block/lot).
- Byte size of a **full** 108-column PLUTO CSV and of a cold ACRIS Parties extract.
- A complete PAD file. Portal and guessed `s-media` zip URLs 403/404 from this environment (2026-09-17). Official layout is `padlayout.pdf` (`billboro` / `billblock` / `billlot`). SODA `bc8t-ecyu` remains 403. Mapper is fixture-tested; live join is exact-BBL until a PAD extract is on disk.
- Staten Island deeds as `DEED`. The 2026-09-17 sale-type Master extract overlaps 194,407 unique SI legal `document_id`s in **one** row. A live lookup of eight SI legal IDs returned `RPTT` (transfer tax) on every one. `RPTT` is official class `OTHER DOCUMENTS`.

---

## 10. Philadelphia OPA property assessments

Retrieval date: **2026-09-17**. Client User-Agent: `opaque-housing/0.1 (residential-ownership-research)`.

| | |
|---|---|
| Portal | https://opendataphilly.org/datasets/philadelphia-properties-and-assessment-history/ |
| Live table | `opa_properties_public` on `https://phl.carto.com/api/v2/sql` |
| Rows (live count by category) | 581,772 including non-res; 522,675 in categories 1/2/3/14 |
| Ingest | `oh ingest --metro phl` |

Verified fields used for `parcels_snapshot`: `parcel_number`, `owner_1`, `owner_2` (not classified), `mailing_street` / `mailing_address_1` / `mailing_city_state` / `mailing_zip`, `category_code`, `category_code_description`, `building_code_description`, `zip_code`, `unit`, `assessment_date`. `census_tract` is 1–3 digits and is **not** mapped to a 2020 GEOID.

Residential categories (live descriptions): 1 Single Family (463,036); 2 Multi Family (41,411); 3 Mixed Use (14,165); 14 Apartments > 4 Units (4,063).

## 11. Philadelphia real estate transfers

| | |
|---|---|
| Portal | https://opendataphilly.org/datasets/real-estate-transfers/ |
| Live table | `rtt_summary` |
| Verified fields | `document_id`, `document_type`, `recording_date`, `grantors`, `grantees`, `total_consideration`, `opa_account_num` |
| Sale type used | `DEED` only (1,102,535 rows). `DEED SHERIFF` / `SHERIFF'S DEED` are not in the headline set |
| Consideration-filtered DEED years | Recording years 2000–2025 are populated at ~18k–39k / year |

## 12. Pennsylvania Department of State businesses

| | |
|---|---|
| Portal | https://data.pa.gov/Licenses-Certificates/Filtered-View-Distinct-Registered-Businesses-in-PA/3urc-uaba |
| Dataset ID | `3urc-uaba` (filter of `xvd7-5r2c`) |
| Rows | 2,360,829 |
| Verified fields | `business_name`, `filing_number`, `address_line1`, `typeofbusinessregistration`, `shortcountyname` |
| Officer names | **None.** O-tiers are not computed for Philadelphia (ADR 0010). |
