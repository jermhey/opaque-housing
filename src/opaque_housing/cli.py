"""Typer CLI. Network and file access for the pipeline live here and in adapters."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import polars as pl
import typer
from dotenv import load_dotenv

from opaque_housing import __version__
from opaque_housing.adapters.http import stream_to_path
from opaque_housing.adapters.nyc.pluto import NycPlutoAdapter
from opaque_housing.adapters.nyc.sources import NYC_SOURCES, PLUTO_SNAPSHOT_DATE
from opaque_housing.classify.apply import classify_parcel_frame
from opaque_housing.classify.pipeline import classify_owner
from opaque_housing.classify.rules import RULES_VERSION
from opaque_housing.labeling.sample import (
    PRIVATE_GOLD_CLASSES,
    assign_splits,
    stratified_owner_sample,
)
from opaque_housing.metrics.correction import bootstrap_corrected_prevalence
from opaque_housing.metrics.evaluation import evaluation_report
from opaque_housing.metrics.stock import headline_shares, private_residential, stock_breakdowns
from opaque_housing.paths import derived_dir, latest_raw_file, raw_dir
from opaque_housing.quality.manifest import RunManifest
from opaque_housing.schema import ENTITY_OWNED_CLASSES, BuildingType, OwnerClass

load_dotenv()

app = typer.Typer(no_args_is_help=True, help="Opaque housing investigation pipeline.")

_ENTITY_VALUES = {item.value for item in ENTITY_OWNED_CLASSES}


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def ingest(
    metro: Annotated[str, typer.Option(help="Metro id, e.g. nyc.")] = "nyc",
    dataset: Annotated[str, typer.Option(help="Source name, or all.")] = "all",
    force: Annotated[bool, typer.Option(help="Re-download even if the file exists.")] = False,
    retrieval_date: Annotated[
        str | None, typer.Option(help="ISO date folder under data/raw/. Default: today.")
    ] = None,
) -> None:
    """Download raw source extracts into data/raw/<metro>/<dataset>/<date>/."""
    if metro != "nyc":
        typer.echo(f"ingest is only wired for nyc (got {metro})", err=True)
        raise typer.Exit(code=1)
    day = date.fromisoformat(retrieval_date) if retrieval_date else date.today()
    names = list(NYC_SOURCES) if dataset == "all" else [dataset]
    for name in names:
        spec = NYC_SOURCES.get(name)
        if spec is None:
            typer.echo(f"unknown dataset {name}", err=True)
            raise typer.Exit(code=1)
        dest = raw_dir(metro, spec.name, day) / spec.filename
        if dest.exists() and not force:
            typer.echo(f"skip existing {dest}")
            continue
        typer.echo(f"downloading {spec.dataset_id} -> {dest}")
        stream_to_path(spec.csv_url, dest)
        typer.echo(f"wrote {dest} ({dest.stat().st_size} bytes)")


@app.command()
def build(
    metro: Annotated[str, typer.Option(help="Metro id, e.g. nyc.")] = "nyc",
    source: Annotated[
        Path | None, typer.Option(help="PLUTO extract. Default: latest ingested raw file.")
    ] = None,
    equiv: Annotated[Path | None, typer.Option(help="Tract-NTA equivalency CSV.")] = None,
    out_dir: Annotated[Path | None, typer.Option(help="Derived output directory.")] = None,
    snapshot_date: Annotated[
        str, typer.Option(help="Canonical snapshot date.")
    ] = PLUTO_SNAPSHOT_DATE,
    gold: Annotated[
        Path | None,
        typer.Option(help="Optional labeled gold CSV for Rogan–Gladen correction."),
    ] = None,
) -> None:
    """Classify residential parcels and write stock shares."""
    if metro != "nyc":
        typer.echo(f"build is only wired for nyc (got {metro})", err=True)
        raise typer.Exit(code=1)
    source_path = source or latest_raw_file(metro, "pluto", NYC_SOURCES["pluto"].filename)
    if source_path is None or not source_path.exists():
        typer.echo("no PLUTO extract; pass --source or run oh ingest", err=True)
        raise typer.Exit(code=1)
    equiv_path = equiv or latest_raw_file(metro, "tract_nta", NYC_SOURCES["tract_nta"].filename)
    dest = out_dir or derived_dir(metro)
    dest.mkdir(parents=True, exist_ok=True)

    started = datetime.now(tz=UTC)
    adapter = NycPlutoAdapter(
        snapshot_date=date.fromisoformat(snapshot_date),
        tract_equiv_path=equiv_path,
    )
    parcels = adapter.load_parcels_snapshot(source_path)
    classified = classify_parcel_frame(parcels)
    private, private_count = private_residential(classified)
    headlines = headline_shares(private)
    breakdowns = stock_breakdowns(private)

    labeled = _read_labeled_gold(gold) if gold else None
    if labeled:
        test_only = [row for row in labeled if row.get("split") == "test"]
        labeled = test_only or labeled
    correction = _correction_block(headlines, labeled) if labeled else None
    if correction:
        headlines = {**headlines, "correction": correction}

    classified.write_parquet(dest / "parcels_classified.parquet")
    for name, table in breakdowns.items():
        table.write_csv(dest / f"stock_{name}.csv")
    (dest / "headlines.json").write_text(json.dumps(headlines, indent=2) + "\n")

    versions = sorted(classified["source_version"].drop_nulls().unique().to_list())
    manifest = RunManifest(
        metro_id=metro,
        started_at=started.isoformat(),
        finished_at=datetime.now(tz=UTC).isoformat(),
        source_paths={
            "pluto": str(source_path),
            "tract_nta": str(equiv_path) if equiv_path else "",
        },
        source_versions={"pluto": ",".join(versions)},
        rules_version=RULES_VERSION,
        filter_counts=[*adapter.filter_counts, private_count],
        notes=[
            "raw shares only" if correction is None else "raw shares plus gold-set correction",
            "trusts are not in the entity headline",
        ],
    )
    (dest / "run_manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2) + "\n")
    typer.echo(f"wrote {dest} parcels={classified.height} private={private.height}")


@app.command("eval")
def eval_cmd(
    gold: Annotated[Path, typer.Option(help="Labeled gold CSV.")] = Path("eval/gold/ci_dev.csv"),
    baseline: Annotated[Path, typer.Option(help="Stored macro-F1 baseline.")] = Path(
        "eval/reports/baseline_macro_f1.json"
    ),
    split: Annotated[str, typer.Option(help="dev, test, or all.")] = "test",
    out: Annotated[Path, typer.Option(help="Report JSON.")] = Path("eval/reports/rules_eval.json"),
) -> None:
    """Compare rule predictions to gold labels. CI fails if test macro-F1 drops."""
    rows = _read_labeled_gold(gold)
    if split != "all":
        rows = [row for row in rows if row.get("split", split) == split]
    if not rows:
        typer.echo(f"no labeled rows in {gold} for split={split}", err=True)
        raise typer.Exit(code=1)
    y_true = [row["owner_class"] for row in rows]
    y_pred = [_predict_class(row["name_raw"], row.get("building_type")) for row in rows]
    report = evaluation_report(y_true, y_pred)
    report["split"] = split
    report["gold"] = str(gold)
    report["rules_version"] = RULES_VERSION
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    macro_f1_value = report["macro_f1"]
    if not isinstance(macro_f1_value, float):
        raise TypeError("macro_f1 must be float")
    typer.echo(f"macro_f1={macro_f1_value:.4f} n={report['n']} -> {out}")
    if baseline.exists():
        stored = json.loads(baseline.read_text())
        threshold = float(stored["value"])
        if macro_f1_value < threshold:
            typer.echo(
                f"macro_f1 {macro_f1_value:.4f} is below baseline {threshold:.4f}",
                err=True,
            )
            raise typer.Exit(code=1)


@app.command()
def publish() -> None:
    """Publish aggregate parquet/csv. Not wired in Milestone 1."""
    typer.echo("publish is not implemented", err=True)
    raise typer.Exit(code=1)


@app.command()
def label(
    queue: Annotated[Path, typer.Option(help="Labeling queue CSV.")] = Path("eval/gold/queue.csv"),
    sample_from: Annotated[
        Path | None,
        typer.Option(help="Classified parcels parquet; write a new stratified queue."),
    ] = None,
    n: Annotated[int, typer.Option(help="Target gold-set size.")] = 600,
    seed: Annotated[int, typer.Option(help="Sampling seed.")] = 20260916,
) -> None:
    """Build a stratified gold queue, or label the next unlabeled row."""
    if sample_from is not None:
        classified = pl.read_parquet(sample_from)
        sample = assign_splits(stratified_owner_sample(classified, n=n, seed=seed), seed=seed)
        _write_queue(queue, sample)
        private_path = queue.parent / "individuals" / "queue.csv"
        private_rows = sample.filter(pl.col("owner_class").is_in(list(PRIVATE_GOLD_CLASSES)))
        if private_rows.height:
            private_path.parent.mkdir(parents=True, exist_ok=True)
            _write_queue(private_path, private_rows)
        typer.echo(f"wrote {queue} n={sample.height}")
        typer.echo(
            "Individuals/trusts/estates also copied under eval/gold/individuals/ (gitignored)."
        )
        return
    if not queue.exists():
        typer.echo(f"missing queue {queue}; pass --sample-from to create one", err=True)
        raise typer.Exit(code=1)
    table = pl.read_csv(queue, infer_schema_length=0)
    if "label" not in table.columns:
        table = table.with_columns(pl.lit("").alias("label"))
    rows = table.iter_rows(named=True)
    pending = [i for i, row in enumerate(rows) if not str(row.get("label") or "").strip()]
    if not pending:
        typer.echo("queue is fully labeled")
        return
    classes = ", ".join(item.value for item in OwnerClass)
    updated = table.to_dicts()

    def persist() -> int:
        pl.DataFrame(updated).write_csv(queue)
        return sum(1 for row in updated if not str(row.get("label") or "").strip())

    for offset, index in enumerate(pending, start=1):
        row = updated[index]
        typer.echo(
            f"[{offset}/{len(pending)}] {row.get('name_normalized') or row.get('name_raw')}  "
            f"pred={row.get('owner_class')}  type={row.get('building_type')}  "
            f"borough={row.get('geo_borough')}  rule={row.get('rule_id')}  split={row.get('split')}"
        )
        while True:
            answer = typer.prompt(f"class [{row.get('owner_class')}] or s=skip, q=quit, ?=list")
            text = answer.strip().lower()
            if text in {"q", "quit"}:
                remaining = persist()
                typer.echo(f"saved {queue}; unlabeled remaining={remaining}")
                return
            if text in {"s", "skip"}:
                break
            if text in {"?", "help"}:
                typer.echo(classes)
                continue
            if not text:
                text = str(row.get("owner_class") or "")
            try:
                OwnerClass(text)
            except ValueError:
                typer.echo(f"unknown class {text}; expected one of: {classes}")
                continue
            updated[index]["label"] = text
            updated[index]["labeled_at"] = datetime.now(tz=UTC).isoformat()
            persist()
            break
    remaining = persist()
    typer.echo(f"saved {queue}; unlabeled remaining={remaining}")


def _predict_class(name_raw: str | None, building_type: str | None) -> str:
    parsed = BuildingType(building_type) if building_type else None
    return classify_owner(name_raw, parsed).owner_class.value


def _read_labeled_gold(path: Path) -> list[dict[str, str]]:
    table = pl.read_csv(path, infer_schema_length=0)
    label_col = "label" if "label" in table.columns else "owner_class"
    rows: list[dict[str, str]] = []
    for row in table.iter_rows(named=True):
        label = str(row.get(label_col) or "").strip()
        if not label:
            continue
        rows.append(
            {
                "name_raw": str(row.get("name_raw") or row.get("owner_name_raw") or ""),
                "building_type": str(row.get("building_type") or ""),
                "owner_class": label,
                "split": str(row.get("split") or ""),
            }
        )
    return rows


_ENTITY_PLUS_TRUST = _ENTITY_VALUES | {OwnerClass.TRUST.value}
_HEADLINE_INCLUDES_TRUST = {
    "private_all_entity_plus_trust",
    "sfr_condo_entity_plus_trust",
}


def _correction_block(
    headlines: dict[str, object],
    labeled: list[dict[str, str]],
) -> dict[str, object]:
    block: dict[str, object] = {}
    for key, payload in headlines.items():
        if not isinstance(payload, dict) or "unit_share" not in payload:
            continue
        positive = _ENTITY_PLUS_TRUST if key in _HEADLINE_INCLUDES_TRUST else _ENTITY_VALUES
        y_true = [row["owner_class"] in positive for row in labeled]
        y_pred = [
            _predict_class(row["name_raw"], row.get("building_type")) in positive for row in labeled
        ]
        block[key] = {
            "unit": bootstrap_corrected_prevalence(float(payload["unit_share"]), y_true, y_pred),
            "parcel": bootstrap_corrected_prevalence(
                float(payload["parcel_share"]), y_true, y_pred
            ),
            "n_labeled": len(labeled),
            "positive_includes_trust": key in _HEADLINE_INCLUDES_TRUST,
        }
    return block


def _write_queue(path: Path, sample: pl.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keep = [
        name
        for name in (
            "name_normalized",
            "owner_name_raw",
            "owner_key",
            "building_type",
            "geo_borough",
            "rule_id",
            "owner_class",
            "split",
        )
        if name in sample.columns
    ]
    rename = {"owner_name_raw": "name_raw"} if "owner_name_raw" in keep else {}
    out = sample.select(keep).rename(rename)
    if "name_raw" not in out.columns and "name_normalized" in out.columns:
        out = out.with_columns(pl.col("name_normalized").alias("name_raw"))
    out = out.with_columns(pl.lit("").alias("label"), pl.lit("").alias("labeled_at"))
    out.write_csv(path)
