import json
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

from opaque_housing.app.main import create_app
from opaque_housing.app.store import AggregateStore, collect_keys
from opaque_housing.metrics.publish import FORBIDDEN_COLUMNS, PublishError


def _headlines(parcel_share: float = 0.1) -> dict:
    return {
        "private_all_entity_only": {
            "parcels": 100,
            "units": 200,
            "entity_parcels": 10,
            "entity_units": 40,
            "parcel_share": parcel_share,
            "unit_share": 0.2,
        },
        "private_all_entity_plus_trust": {
            "parcels": 100,
            "units": 200,
            "entity_parcels": 15,
            "entity_units": 50,
            "parcel_share": 0.15,
            "unit_share": 0.25,
        },
        "sfr_condo_entity_only": {
            "parcels": 80,
            "units": 90,
            "entity_parcels": 8,
            "entity_units": 9,
            "parcel_share": 0.1,
            "unit_share": 0.1,
        },
        "sfr_condo_entity_plus_trust": {
            "parcels": 80,
            "units": 90,
            "entity_parcels": 12,
            "entity_units": 14,
            "parcel_share": 0.15,
            "unit_share": 0.155,
        },
    }


def _type_csv(path: Path, llc_sfr: int, llc_mf: int, sfr: int, mf: int) -> None:
    pl.DataFrame(
        {
            "building_type": ["sfr_1_4", "sfr_1_4", "large_mf", "large_mf"],
            "owner_class": ["llc", "individual", "llc", "individual"],
            "class_parcels": [llc_sfr, sfr - llc_sfr, llc_mf, mf - llc_mf],
            "class_units": [llc_sfr, sfr - llc_sfr, llc_mf * 10, (mf - llc_mf) * 10],
            "parcels": [sfr, sfr, mf, mf],
            "units": [sfr, sfr, mf * 10, mf * 10],
        }
    ).write_csv(path)


def _write_published(root: Path) -> None:
    for metro, share, types in (
        ("nyc", 0.18, (8, 10, 80, 20)),
        ("phl", 0.10, (7, 3, 90, 10)),
    ):
        folder = root / metro
        folder.mkdir(parents=True)
        (folder / "headlines.json").write_text(json.dumps(_headlines(share)) + "\n")
        _type_csv(folder / "stock_by_building_type.csv", *types)
        pl.DataFrame(
            {
                "owner_class": ["llc", "individual"],
                "class_parcels": [10, 90],
                "class_units": [20, 80],
                "parcels": [100, 100],
                "units": [100, 100],
                "parcel_share": [0.1, 0.9],
                "unit_share": [0.2, 0.8],
            }
        ).write_csv(folder / "stock_by_class.csv")
        pl.DataFrame(
            {
                "nta": ["N1"],
                "nta_name": ["Example"],
                "borough": ["Test"],
                "parcels": [100],
                "units": [100],
                "entity_parcels": [10],
                "entity_units": [20],
                "entity_parcel_share": [0.1],
                "entity_unit_share": [0.2],
                "sfr_condo_parcels": [80],
                "sfr_condo_units": [80],
                "sfr_condo_entity_parcels": [8],
                "sfr_condo_entity_units": [8],
                "sfr_condo_entity_unit_share": [0.1],
                "suppressed": [False],
            }
        ).write_csv(folder / "neighborhoods.csv")
        pl.DataFrame(
            {
                "geo_neighborhood": ["N1"],
                "parcels": [100],
                "units": [100],
                "n_name_keys": [12],
                "hhi_parcels": [0.12],
                "hhi_units": [0.15],
                "top5_parcel_share": [0.4],
                "top5_unit_share": [0.5],
                "top10_parcel_share": [0.6],
                "top10_unit_share": [0.7],
                "top20_parcel_share": [0.8],
                "top20_unit_share": [0.9],
                "suppressed": [False],
            }
        ).write_csv(folder / "concentration_by_neighborhood.csv")
        pl.DataFrame(
            {
                "config": ["default_10k", "threshold_0", "threshold_100k", "exclude_sheriff"],
                "min_consideration": [10000.0, 0.0, 100000.0, 10000.0],
                "sales": [100, 120, 80, 90],
                "entity_sales": [20, 22, 10, 15],
                "sale_share": [0.2, 0.183, 0.125, 0.167],
                "units": [200, 240, 160, 180],
                "entity_units": [50, 55, 30, 40],
                "unit_share": [0.25, 0.229, 0.187, 0.222],
            }
        ).write_csv(folder / "flow_sensitivity.csv")
        (folder / "flow_headlines.json").write_text(
            json.dumps(
                {
                    "window": {"start": 2003, "end": 2025},
                    "private_residential": {
                        "sales": 100,
                        "units": 200,
                        "entity_sales": 20,
                        "entity_units": 50,
                        "sale_share": 0.2,
                        "unit_share": 0.25,
                    },
                    "sfr_condo": {
                        "sales": 80,
                        "units": 90,
                        "entity_sales": 12,
                        "entity_units": 14,
                        "sale_share": 0.15,
                        "unit_share": 0.155,
                    },
                }
            )
            + "\n"
        )
        pl.DataFrame(
            {
                "year": [2024],
                "sales": [10],
                "units": [20],
                "entity_sales": [2],
                "entity_units": [5],
                "sale_share": [0.2],
                "unit_share": [0.25],
            }
        ).write_csv(folder / "flow_by_year.csv")
        (folder / "freshness.json").write_text(
            json.dumps(
                {
                    "metro": metro,
                    "generated_at": "2026-09-17T00:00:00+00:00",
                    "flow_present": True,
                    "opacity_present": False,
                    "reused": {},
                }
            )
            + "\n"
        )
        (folder / "run_manifest.json").write_text(
            json.dumps(
                {
                    "metro_id": metro,
                    "filter_counts": [
                        {
                            "stage": "stock_private_denominator",
                            "rule_id": "exclude_public_nonprofit",
                            "rows_in": 110,
                            "rows_out": 100,
                        }
                    ],
                }
            )
            + "\n"
        )


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _write_published(tmp_path)
    monkeypatch.setenv("ADMIN_SECRET", "test-admin-secret")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-32bytes-long")
    return TestClient(create_app(tmp_path))


def _assert_safe(payload: object) -> None:
    leaked = [key for key in collect_keys(payload) if key.lower() in FORBIDDEN_COLUMNS]
    assert leaked == []


def test_store_refuses_owner_key_csv(tmp_path: Path) -> None:
    folder = tmp_path / "nyc"
    folder.mkdir()
    (folder / "headlines.json").write_text("{}\n")
    pl.DataFrame({"owner_key": ["abc"], "units": [1]}).write_csv(folder / "stock_by_class.csv")
    with pytest.raises(PublishError, match="owner_key"):
        AggregateStore(tmp_path)


def test_store_refuses_parcel_file(tmp_path: Path) -> None:
    folder = tmp_path / "nyc"
    folder.mkdir()
    (folder / "parcels_classified.parquet").write_bytes(b"not-a-parquet")
    with pytest.raises(PublishError, match="not a public aggregate"):
        AggregateStore(tmp_path)


def test_v1_stock_flow_mix_and_definition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    metros = client.get("/v1/metros")
    assert metros.status_code == 200
    assert set(metros.json()["metros"]) == {"nyc", "phl"}
    stock = client.get("/v1/nyc/stock")
    assert stock.status_code == 200
    _assert_safe(stock.json())
    mix = client.get("/v1/compare/mix")
    assert mix.status_code == 200
    body = mix.json()
    _assert_safe(body)
    assert body["mix"]["gap_common"] == pytest.approx(
        body["mix"]["rate_effect"] + body["mix"]["mix_effect"]
    )
    definition = client.get(
        "/v1/phl/definition",
        params={
            "series": "sfr_condo",
            "weight": "parcel",
            "include_trust": True,
            "flow_config": "exclude_sheriff",
        },
    )
    assert definition.status_code == 200
    _assert_safe(definition.json())
    assert definition.json()["flow"]["config"] == "exclude_sheriff"
    hoods = client.get("/v1/nyc/neighborhoods")
    assert hoods.status_code == 200
    _assert_safe(hoods.json())
    assert hoods.json()["has_concentration"] is True
    assert "owner_key" not in json.dumps(hoods.json())


def test_no_public_lookup_routes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/v1/nyc/search?q=main").status_code == 404
    assert client.get("/v1/lookup?address=1+Main").status_code == 404
    assert client.get("/search").status_code == 404


def test_htmx_home_and_definitions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    home = client.get("/")
    assert home.status_code == 200
    assert "PHL on NYC mix" in home.text
    assert "No name or address search" in home.text
    defs = client.get("/definitions", params={"metro": "phl", "flow_config": "exclude_sheriff"})
    assert defs.status_code == 200
    assert "Definition playground" in defs.text
    hoods = client.get("/neighborhoods", params={"metro": "nyc"})
    assert hoods.status_code == 200
    assert "Anonymous concentration" in hoods.text


def test_admin_requires_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    denied = client.get("/admin", follow_redirects=False)
    assert denied.status_code in {303, 307, 401}
    bad = client.post("/admin/login", data={"password": "nope"}, follow_redirects=False)
    assert bad.status_code == 303
    ok = client.post("/admin/login", data={"password": "test-admin-secret"}, follow_redirects=False)
    assert ok.status_code == 303
    page = client.get("/admin")
    assert page.status_code == 200
    assert "Dispatch refresh.yml" in page.text
    refresh = client.post("/admin/refresh")
    assert refresh.status_code == 200
    assert "gh workflow run refresh.yml" in refresh.text


def test_published_tree_api_has_no_forbidden_keys() -> None:
    root = Path("data/published")
    if not (root / "nyc" / "headlines.json").exists():
        pytest.skip("published NYC aggregates not in the workspace")
    client = TestClient(create_app(root))
    for path in (
        "/v1/nyc/stock",
        "/v1/phl/stock",
        "/v1/nyc/flow",
        "/v1/phl/flow",
        "/v1/compare/mix",
        "/v1/freshness",
        "/v1/nyc/neighborhoods",
        "/v1/phl/neighborhoods",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        _assert_safe(response.json())
    home = client.get("/")
    assert home.status_code == 200
    assert "PHL on NYC mix" in home.text
    trends = client.get("/trends", params={"metro": "phl"})
    assert trends.status_code == 200
    assert "Sale-flow trends" in trends.text
    hoods = client.get("/neighborhoods")
    assert hoods.status_code == 200
    assert "Greenpoint" in hoods.text
    assert "26,719" in hoods.text
