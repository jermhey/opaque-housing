import json
from pathlib import Path

import polars as pl
import pytest

from opaque_housing.metrics.publish import (
    PublishError,
    assert_safe_columns,
    assert_stock_stable,
    forbidden_columns,
    neighborhood_table,
    nta_name_lookup,
    reattach_correction,
    sanitize_manifest,
    stock_change_ratio,
)
from opaque_housing.metrics.stock import MIN_PUBLISH_UNITS


def _nta_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "geo_neighborhood": ["QN0104", "QN0104", "MN1203", "MN1203"],
            "building_type": ["sfr_1_4", "sfr_1_4", "other_res", "other_res"],
            "owner_class": ["llc", "individual", "llc", "individual"],
            "class_parcels": [10, 90, 1, 1],
            "class_units": [20, 80, 2, 1],
            "parcels": [100, 100, 2, 2],
            "units": [100, 100, 3, 3],
        }
    )


def test_forbidden_columns_are_exact() -> None:
    assert forbidden_columns(["owner_class", "units"]) == []
    assert forbidden_columns(["owner_key", "nta_name"]) == ["owner_key"]
    with pytest.raises(PublishError, match="owner_name"):
        assert_safe_columns(["owner_name", "units"], origin="leaky.csv")


def test_neighborhood_rollup_suppresses_small_cells() -> None:
    names = nta_name_lookup(
        pl.DataFrame(
            {
                "ntacode": ["QN0104", "MN1203"],
                "ntaname": ["Astoria", "Tiny Park"],
                "boroname": ["Queens", "Manhattan"],
            }
        )
    )
    table = neighborhood_table(_nta_rows(), names, min_units=MIN_PUBLISH_UNITS)
    astoria = table.filter(pl.col("nta") == "QN0104").row(0, named=True)
    tiny = table.filter(pl.col("nta") == "MN1203").row(0, named=True)
    assert astoria["nta_name"] == "Astoria"
    assert astoria["borough"] == "Queens"
    assert astoria["suppressed"] is False
    assert astoria["entity_unit_share"] == pytest.approx(0.2)
    assert astoria["sfr_condo_entity_unit_share"] == pytest.approx(0.2)
    assert tiny["suppressed"] is True
    assert tiny["entity_unit_share"] is None
    assert tiny["units"] == 3


def test_stock_change_gate() -> None:
    assert stock_change_ratio(100, 110) == pytest.approx(0.1)
    assert_stock_stable(100, 110, max_change=0.2)
    with pytest.raises(PublishError, match="changed"):
        assert_stock_stable(100, 130, max_change=0.2)


def test_sanitize_manifest_drops_local_paths() -> None:
    cleaned = sanitize_manifest(
        {
            "metro_id": "nyc",
            "started_at": "2026-09-17T00:00:00+00:00",
            "source_paths": {"pluto": "/secret/pluto.csv"},
            "source_versions": {"pluto": "26v2"},
            "notes": ["ok"],
        }
    )
    assert "source_paths" not in cleaned
    assert cleaned["source_versions"] == {"pluto": "26v2"}


def test_reattach_correction_applies_stored_rates() -> None:
    headlines = {
        "private_all_entity_only": {
            "parcels": 100,
            "units": 1000,
            "parcel_share": 0.2,
            "unit_share": 0.4,
        }
    }
    previous = {
        "correction": {
            "private_all_entity_only": {
                "n_labeled": 305,
                "positive_includes_trust": False,
                "unit": {
                    "sensitivity": 0.97,
                    "specificity": 0.98,
                    "n_labeled": 305.0,
                },
                "parcel": {
                    "sensitivity": 0.97,
                    "specificity": 0.98,
                    "n_labeled": 305.0,
                },
            }
        }
    }
    updated = reattach_correction(headlines, previous)
    unit = updated["correction"]["private_all_entity_only"]["unit"]
    assert unit["observed"] == 0.4
    assert unit["corrected"] == pytest.approx((0.4 + 0.98 - 1.0) / (0.97 + 0.98 - 1.0))
    assert unit["corrected_lo"] is None
    assert updated["correction"]["private_all_entity_only"]["rates_reused"] is True


def test_cli_publish_writes_only_aggregates(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from opaque_housing.cli import app

    derived = tmp_path / "derived"
    built = CliRunner().invoke(
        app,
        [
            "build",
            "--metro",
            "nyc",
            "--source",
            "tests/fixtures/nyc/pluto_sample.csv",
            "--equiv",
            "tests/fixtures/nyc/tract_nta_equiv_sample.csv",
            "--out-dir",
            str(derived),
        ],
    )
    assert built.exit_code == 0, built.stdout + built.stderr
    (derived / "owner_links.csv").write_text("owner_key,evidence_ref\nabc,Mark\n")
    dest = tmp_path / "published"
    site = tmp_path / "site-data"
    published = CliRunner().invoke(
        app,
        [
            "publish",
            "--metro",
            "nyc",
            "--derived",
            str(derived),
            "--out-dir",
            str(dest),
            "--site-data",
            str(site),
            "--equiv",
            "tests/fixtures/nyc/tract_nta_equiv_sample.csv",
        ],
    )
    assert published.exit_code == 0, published.stdout + published.stderr
    assert not (dest / "owner_links.csv").exists()
    assert not (dest / "parcels_classified.parquet").exists()
    assert (dest / "site.json").exists()
    assert (dest / "neighborhoods.csv").exists()
    assert (site / "headlines.json").exists()
    payload = json.loads((dest / "site.json").read_text())
    assert payload["metro"] == "nyc"
    assert payload["neighborhoods"]
    text = " ".join(path.read_text() for path in dest.glob("*.csv"))
    assert "owner_key" not in text
    assert "firstname" not in text.lower()
