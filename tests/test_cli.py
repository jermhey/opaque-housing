from pathlib import Path

from typer.testing import CliRunner

from opaque_housing.cli import app

runner = CliRunner()
FIXTURE = Path("tests/fixtures/nyc/pluto_sample.csv")
EQUIV = Path("tests/fixtures/nyc/tract_nta_equiv_sample.csv")


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.stdout
    assert "build" in result.stdout
    assert "label" in result.stdout
    assert "eval" in result.stdout


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
