"""One-off source probe for M0. Not imported by src."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx

UA = "opaque-housing/0.1 (residential-ownership-research)"
OUT = Path(__file__).resolve().parent / "source_probe"
OUT.mkdir(exist_ok=True)
TODAY = date.today().isoformat()

DATASETS = {
    "nyc_pluto": ("https://data.cityofnewyork.us", "64uk-42ks"),
    "nyc_mappluto": ("https://data.cityofnewyork.us", "f888-ni5f"),
    "nyc_dof_bldgclass": ("https://data.cityofnewyork.us", "nzvw-cjc2"),
    "nyc_acris_master": ("https://data.cityofnewyork.us", "bnx9-e6tj"),
    "nyc_acris_legals": ("https://data.cityofnewyork.us", "8h5j-fqxa"),
    "nyc_acris_parties": ("https://data.cityofnewyork.us", "636b-3b5g"),
    "nyc_acris_doc_codes": ("https://data.cityofnewyork.us", "7isb-wh4c"),
    "nyc_hpd_registrations": ("https://data.cityofnewyork.us", "tesw-yqqr"),
    "nyc_hpd_contacts": ("https://data.cityofnewyork.us", "feu5-w2e2"),
    "nyc_nta2020": ("https://data.cityofnewyork.us", "9nt8-h7nd"),
    "nyc_tract_nta_equiv": ("https://data.cityofnewyork.us", "hm78-6dwm"),
    "nyc_pad": ("https://data.cityofnewyork.us", "bc8t-ecyu"),
    "nys_active_corps": ("https://data.ny.gov", "n9v6-gdp6"),
    "nys_name_status_history": ("https://data.ny.gov", "ekwr-p59j"),
}


def get(client: httpx.Client, url: str, params: dict[str, str] | None = None) -> httpx.Response:
    r = client.get(url, params=params)
    r.raise_for_status()
    return r


def summarize_view(view: dict) -> dict:
    cols = []
    for col in view.get("columns", []):
        if col.get("flags") and "hidden" in col.get("flags", []):
            continue
        cols.append(
            {
                "field": col.get("fieldName"),
                "name": col.get("name"),
                "type": col.get("dataTypeName"),
                "description": (col.get("description") or "")[:240],
            }
        )
    return {
        "id": view.get("id"),
        "name": view.get("name"),
        "attribution": view.get("attribution"),
        "description": (view.get("description") or "")[:800],
        "rowsUpdatedAt": view.get("rowsUpdatedAt"),
        "viewLastModified": view.get("viewLastModified"),
        "createdAt": view.get("createdAt"),
        "downloadCount": view.get("downloadCount"),
        "n_columns": len(cols),
        "columns": cols,
        "metadata_row_count": (view.get("columns") or [{}])[0].get("cachedContents", {}),
    }


def main() -> None:
    headers = {"User-Agent": UA, "Accept": "application/json"}
    with httpx.Client(headers=headers, timeout=90.0, follow_redirects=True) as client:
        for key, (host, dsid) in DATASETS.items():
            print(f"== {key} {dsid}")
            summary: dict = {"probe_date": TODAY, "host": host, "id": dsid}
            try:
                view = get(client, f"{host}/api/views/{dsid}.json").json()
                summary["view"] = summarize_view(view)
                (OUT / f"{key}_view.json").write_text(json.dumps(summary["view"], indent=2))
            except Exception as exc:
                summary["view_error"] = repr(exc)
                print("  view error", exc)
                (OUT / f"{key}_summary.json").write_text(json.dumps(summary, indent=2, default=str))
                continue
            try:
                count = get(
                    client,
                    f"{host}/resource/{dsid}.json",
                    params={"$select": "count(*) as n"},
                ).json()
                summary["row_count"] = count
            except Exception as exc:
                summary["count_error"] = repr(exc)
                print("  count error", exc)
            try:
                sample = get(
                    client,
                    f"{host}/resource/{dsid}.json",
                    params={"$limit": "3"},
                ).json()
                summary["sample"] = sample
                (OUT / f"{key}_sample.json").write_text(json.dumps(sample, indent=2))
            except Exception as exc:
                summary["sample_error"] = repr(exc)
                print("  sample error", exc)
            (OUT / f"{key}_summary.json").write_text(json.dumps(summary, indent=2, default=str))
            print("  rows", summary.get("row_count"), "cols", summary["view"].get("n_columns"))

    print("wrote", OUT)


if __name__ == "__main__":
    main()
