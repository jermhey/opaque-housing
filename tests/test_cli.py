from pathlib import Path

from typer.testing import CliRunner

from opaque_housing.cli import app

runner = CliRunner()
FIXTURE = Path("tests/fixtures/nyc/pluto_sample.csv")
EQUIV = Path("tests/fixtures/nyc/tract_nta_equiv_sample.csv")
MASTER = Path("tests/fixtures/nyc/acris_master.csv")
LEGALS = Path("tests/fixtures/nyc/acris_legals.csv")
PARTIES = Path("tests/fixtures/nyc/acris_parties.csv")
PAD = Path("tests/fixtures/nyc/pad_bbl_sample.csv")
HPD_REGS = Path("tests/fixtures/nyc/hpd_registrations.csv")
HPD_CONTACTS = Path("tests/fixtures/nyc/hpd_contacts.csv")
DOS = Path("tests/fixtures/nyc/nys_dos.csv")


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.stdout
    assert "build" in result.stdout
    assert "label" in result.stdout
    assert "eval" in result.stdout
    assert "flow" in result.stdout
    assert "opacity" in result.stdout
    assert "publish" in result.stdout
    assert "serve" in result.stdout
    assert "worker" in result.stdout
    assert "raw" in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_build_and_eval_on_committed_fixtures(tmp_path: Path) -> None:
    out = tmp_path / "derived"
    built = runner.invoke(
        app,
        [
            "build",
            "--metro",
            "nyc",
            "--source",
            str(FIXTURE),
            "--equiv",
            str(EQUIV),
            "--out-dir",
            str(out),
        ],
    )
    assert built.exit_code == 0, built.stdout + built.stderr
    assert (out / "headlines.json").exists()
    assert (out / "run_manifest.json").exists()
    assert (out / "parcels_classified.parquet").exists()

    report = tmp_path / "eval.json"
    evaluated = runner.invoke(
        app,
        [
            "eval",
            "--gold",
            "eval/gold/ci_dev.csv",
            "--baseline",
            "eval/reports/baseline_macro_f1.json",
            "--split",
            "test",
            "--out",
            str(report),
        ],
    )
    assert evaluated.exit_code == 0, evaluated.stdout + evaluated.stderr
    assert report.exists()


def test_label_sample_from_build(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    runner.invoke(
        app,
        [
            "build",
            "--source",
            str(FIXTURE),
            "--equiv",
            str(EQUIV),
            "--out-dir",
            str(derived),
        ],
    )
    queue = tmp_path / "queue.csv"
    sampled = runner.invoke(
        app,
        [
            "label",
            "--sample-from",
            str(derived / "parcels_classified.parquet"),
            "--queue",
            str(queue),
            "--n",
            "4",
        ],
    )
    assert sampled.exit_code == 0, sampled.stdout + sampled.stderr
    assert queue.exists()
    assert "label" in queue.read_text()


def test_label_reprompts_on_typo_and_saves(tmp_path: Path) -> None:
    queue = tmp_path / "queue.csv"
    queue.write_text(
        "name_normalized,name_raw,owner_key,building_type,geo_borough,"
        "rule_id,owner_class,split,label,labeled_at\n"
        "ACME LLC,ACME LLC,abc123,sfr_1_4,Brooklyn,R080_llc,llc,dev,,\n"
    )
    labeled = runner.invoke(
        app,
        ["label", "--queue", str(queue)],
        input="unkown\nllc\n",
    )
    assert labeled.exit_code == 0, labeled.stdout + labeled.stderr
    assert "unknown class unkown" in labeled.stdout
    text = queue.read_text()
    assert ",llc," in text
    assert "2026-" in text or "T" in text


def test_flow_on_committed_fixtures(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    built = runner.invoke(
        app,
        [
            "build",
            "--source",
            str(FIXTURE),
            "--equiv",
            str(EQUIV),
            "--out-dir",
            str(derived),
        ],
    )
    assert built.exit_code == 0, built.stdout + built.stderr
    flowed = runner.invoke(
        app,
        [
            "flow",
            "--master",
            str(MASTER),
            "--legals",
            str(LEGALS),
            "--parties",
            str(PARTIES),
            "--parcels",
            str(derived / "parcels_classified.parquet"),
            "--pad",
            str(PAD),
            "--out-dir",
            str(derived),
        ],
    )
    assert flowed.exit_code == 0, flowed.stdout + flowed.stderr
    assert (derived / "flow_headlines.json").exists()
    assert (derived / "flow_sensitivity.csv").exists()
    assert (derived / "history_by_year.csv").exists()
    assert (derived / "consistency.json").exists()
    assert (derived / "flow_manifest.json").exists()


def test_opacity_on_committed_fixtures(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    built = runner.invoke(
        app,
        [
            "build",
            "--source",
            str(FIXTURE),
            "--equiv",
            str(EQUIV),
            "--out-dir",
            str(derived),
        ],
    )
    assert built.exit_code == 0, built.stdout + built.stderr
    review = tmp_path / "review.md"
    result = runner.invoke(
        app,
        [
            "opacity",
            "--parcels",
            str(derived / "parcels_classified.parquet"),
            "--registrations",
            str(HPD_REGS),
            "--contacts",
            str(HPD_CONTACTS),
            "--dos",
            str(DOS),
            "--out-dir",
            str(derived),
            "--review-out",
            str(review),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert (derived / "opacity_headlines.json").exists()
    assert (derived / "opacity_manifest.json").exists()
    assert review.exists()
    assert "entity names" in review.read_text().lower()


def test_phl_build_and_publish(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    built = runner.invoke(
        app,
        [
            "build",
            "--metro",
            "phl",
            "--source",
            "tests/fixtures/phl/opa_sample.csv",
            "--out-dir",
            str(derived),
        ],
    )
    assert built.exit_code == 0, built.stdout + built.stderr
    assert (derived / "headlines.json").exists()
    assert (derived / "concentration_by_neighborhood.csv").exists()
    dest = tmp_path / "published"
    published = runner.invoke(
        app,
        [
            "publish",
            "--metro",
            "phl",
            "--derived",
            str(derived),
            "--out-dir",
            str(dest),
            "--site-data",
            str(tmp_path / "site-phl"),
        ],
    )
    assert published.exit_code == 0, published.stdout + published.stderr
    assert (dest / "site.json").exists()
    assert (dest / "neighborhoods.csv").exists()

    flowed = runner.invoke(
        app,
        [
            "flow",
            "--metro",
            "phl",
            "--rtt",
            "tests/fixtures/phl/rtt_sample.csv",
            "--parcels",
            str(derived / "parcels_classified.parquet"),
            "--out-dir",
            str(derived),
        ],
    )
    assert flowed.exit_code == 0, flowed.stdout + flowed.stderr
    assert (derived / "flow_headlines.json").exists()
    assert (derived / "flow_by_year.csv").exists()


def test_cook_build_flow_and_publish(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    built = runner.invoke(
        app,
        [
            "build",
            "--metro",
            "cook",
            "--source",
            "tests/fixtures/cook/universe.csv",
            "--addresses",
            "tests/fixtures/cook/addresses.csv",
            "--characteristics",
            "tests/fixtures/cook/characteristics.csv",
            "--condo",
            "tests/fixtures/cook/condo.csv",
            "--out-dir",
            str(derived),
        ],
    )
    assert built.exit_code == 0, built.stdout + built.stderr
    assert (derived / "headlines.json").exists()
    dest = tmp_path / "published"
    published = runner.invoke(
        app,
        [
            "publish",
            "--metro",
            "cook",
            "--derived",
            str(derived),
            "--out-dir",
            str(dest),
            "--site-data",
            str(tmp_path / "site-cook"),
        ],
    )
    assert published.exit_code == 0, published.stdout + published.stderr
    assert (dest / "site.json").exists()
    flowed = runner.invoke(
        app,
        [
            "flow",
            "--metro",
            "cook",
            "--sales",
            "tests/fixtures/cook/sales.csv",
            "--parcels",
            str(derived / "parcels_classified.parquet"),
            "--out-dir",
            str(derived),
        ],
    )
    assert flowed.exit_code == 0, flowed.stdout + flowed.stderr
    assert (derived / "flow_headlines.json").exists()


def test_dade_build_flow_and_publish(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    built = runner.invoke(
        app,
        [
            "build",
            "--metro",
            "dade",
            "--source",
            "tests/fixtures/dade/gis_sample.csv",
            "--out-dir",
            str(derived),
        ],
    )
    assert built.exit_code == 0, built.stdout + built.stderr
    assert (derived / "headlines.json").exists()
    dest = tmp_path / "published"
    published = runner.invoke(
        app,
        [
            "publish",
            "--metro",
            "dade",
            "--derived",
            str(derived),
            "--out-dir",
            str(dest),
            "--site-data",
            str(tmp_path / "site-dade"),
        ],
    )
    assert published.exit_code == 0, published.stdout + published.stderr
    assert (dest / "site.json").exists()
    flowed = runner.invoke(
        app,
        [
            "flow",
            "--metro",
            "dade",
            "--sdf",
            "tests/fixtures/dade/sdf_sample.csv",
            "--parcels",
            str(derived / "parcels_classified.parquet"),
            "--out-dir",
            str(derived),
        ],
    )
    assert flowed.exit_code == 0, flowed.stdout + flowed.stderr
    assert (derived / "flow_headlines.json").exists()


def test_unknown_metro_asks_for_specs_row() -> None:
    result = runner.invoke(app, ["ingest", "--metro", "lax"])
    assert result.exit_code == 1
    assert "SPECS row" in result.stderr + result.stdout


def test_raw_requires_uri(monkeypatch) -> None:
    monkeypatch.delenv("OH_RAW_URI", raising=False)
    result = runner.invoke(app, ["raw", "push"])
    assert result.exit_code == 1
    assert "OH_RAW_URI" in result.stderr + result.stdout
