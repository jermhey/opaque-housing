"""Coverage queries for M0 data-source notes. Not imported by src."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

UA = "opaque-housing/0.1 (residential-ownership-research)"
OUT = Path(__file__).resolve().parent / "source_probe"
NYC = "https://data.cityofnewyork.us"
NYS = "https://data.ny.gov"


def fetch(client: httpx.Client, host: str, dsid: str, params: dict[str, str]) -> object:
    r = client.get(f"{host}/resource/{dsid}.json", params=params)
    r.raise_for_status()
    return r.json()


def main() -> None:
    headers = {"User-Agent": UA, "Accept": "application/json"}
    results: dict[str, object] = {}
    with httpx.Client(headers=headers, timeout=180.0, follow_redirects=True) as client:
        results["acris_master_span"] = fetch(
            client,
            NYC,
            "bnx9-e6tj",
            {
                "$select": (
                    "min(document_date) as min_document_date,"
                    "max(document_date) as max_document_date,"
                    "min(recorded_datetime) as min_recorded,"
                    "max(recorded_datetime) as max_recorded"
                )
            },
        )
        print("master span", results["acris_master_span"])

        results["acris_master_by_year"] = fetch(
            client,
            NYC,
            "bnx9-e6tj",
            {
                "$select": "date_trunc_y(recorded_datetime) as year, count(*) as n",
                "$group": "year",
                "$order": "year",
            },
        )
        years = results["acris_master_by_year"]
        print("master years", len(years) if isinstance(years, list) else years)

        results["acris_parties_null_name"] = fetch(
            client,
            NYC,
            "636b-3b5g",
            {"$select": "count(*) as n", "$where": "name is null"},
        )
        print("parties null name", results["acris_parties_null_name"])

        results["acris_party_types"] = fetch(
            client,
            NYC,
            "636b-3b5g",
            {"$select": "party_type, count(*) as n", "$group": "party_type", "$order": "party_type"},
        )
        print("party types", results["acris_party_types"])

        results["acris_doc_codes"] = fetch(client, NYC, "7isb-wh4c", {"$limit": "500"})
        print("doc codes", len(results["acris_doc_codes"]) if isinstance(results["acris_doc_codes"], list) else "err")

        results["hpd_reg_span"] = fetch(
            client,
            NYC,
            "tesw-yqqr",
            {
                "$select": (
                    "min(lastregistrationdate) as min_lastreg,"
                    "max(lastregistrationdate) as max_lastreg,"
                    "count(*) as n"
                )
            },
        )
        print("hpd span", results["hpd_reg_span"])

        results["hpd_contact_types"] = fetch(
            client,
            NYC,
            "feu5-w2e2",
            {"$select": "type, count(*) as n", "$group": "type", "$order": "n desc"},
        )
        print("hpd types", results["hpd_contact_types"])

        results["dos_span"] = fetch(
            client,
            NYS,
            "n9v6-gdp6",
            {
                "$select": (
                    "min(initial_dos_filing_date) as min_filed,"
                    "max(initial_dos_filing_date) as max_filed,"
                    "count(*) as n"
                )
            },
        )
        print("dos span", results["dos_span"])

        results["dos_entity_types"] = fetch(
            client,
            NYS,
            "n9v6-gdp6",
            {
                "$select": "entity_type, count(*) as n",
                "$group": "entity_type",
                "$order": "n desc",
            },
        )
        print("dos types", len(results["dos_entity_types"]) if isinstance(results["dos_entity_types"], list) else "err")

        results["name_status_values"] = fetch(
            client,
            NYS,
            "ekwr-p59j",
            {"$select": "name_status, count(*) as n", "$group": "name_status", "$order": "n desc"},
        )
        print("name status", results["name_status_values"])

        results["pluto_ownertype"] = fetch(
            client,
            NYC,
            "64uk-42ks",
            {"$select": "ownertype, count(*) as n", "$group": "ownertype", "$order": "n desc"},
        )
        print("ownertype", results["pluto_ownertype"])

        results["pluto_landuse"] = fetch(
            client,
            NYC,
            "64uk-42ks",
            {"$select": "landuse, count(*) as n", "$group": "landuse", "$order": "landuse"},
        )
        print("landuse", results["pluto_landuse"])

        results["pluto_condo"] = fetch(
            client,
            NYC,
            "64uk-42ks",
            {"$select": "count(*) as n", "$where": "condono is not null"},
        )
        print("condo non-null", results["pluto_condo"])

    (OUT / "coverage.json").write_text(json.dumps(results, indent=2, default=str))
    print("wrote coverage.json")


if __name__ == "__main__":
    main()
