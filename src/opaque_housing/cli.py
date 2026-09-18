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
from opaque_housing.adapters.carto import write_carto_csv
from opaque_housing.adapters.http import stream_to_path
from opaque_housing.adapters.nyc.acris import NycAcrisAdapter
from opaque_housing.adapters.nyc.hpd import NycHpdAdapter
from opaque_housing.adapters.nyc.nys_dos import NycDosAdapter
from opaque_housing.adapters.nyc.pad import load_pad_crosswalk
from opaque_housing.adapters.nyc.pluto import NycPlutoAdapter
from opaque_housing.adapters.nyc.sources import (
    ACRIS_SOURCES,
    HPD_SOURCES,
    NYC_SOURCES,
    NYS_DOS,
    PLUTO_SNAPSHOT_DATE,
    resolve_ingest_specs,
)
from opaque_housing.adapters.phl.opa import PhlOpaAdapter
from opaque_housing.adapters.phl.rtt import PhlRttAdapter
from opaque_housing.adapters.phl.sources import OPA_SNAPSHOT_DATE, resolve_phl_specs
from opaque_housing.adapters.soda import write_soda_parquet
from opaque_housing.classify.apply import classify_parcel_frame
from opaque_housing.classify.llm import apply_llm_label, needs_llm
from opaque_housing.classify.pipeline import classify_owner
from opaque_housing.classify.rules import RULES_VERSION
from opaque_housing.labeling.sample import (
    PRIVATE_GOLD_CLASSES,
    assign_splits,
    stratified_owner_sample,
)
from opaque_housing.metrics.claims import stock_sensitivity_table
from opaque_housing.metrics.concentration import neighborhood_concentration
from opaque_housing.metrics.correction import bootstrap_corrected_prevalence
from opaque_housing.metrics.evaluation import evaluation_report
from opaque_housing.metrics.flow import (
    COVERAGE_WINDOWS,
    PHL_SENSITIVITY_CONFIGS,
    attach_residential,
    classify_buyers,
    flow_breakdowns,
    flow_headlines,
    history_only_sales,
    in_coverage_window,
    sensitivity_table,
    with_year_and_borough,
)
from opaque_housing.metrics.history import consistency_check, historical_stock_table, year_end_dates
from opaque_housing.metrics.opacity import (
    attach_clusters,
    attach_opacity,
    entity_owned,
    opacity_by_type,
    opacity_headlines,
    top_cluster_review,
)
from opaque_housing.metrics.publish import (
    ALLOWED_FILES,
    FORBIDDEN_FILENAMES,
    REQUIRED_FILES,
    PublishError,
    assemble_site_payload,
    assert_allowed_filename,
    assert_safe_columns,
    assert_stock_stable,
    borough_table,
    neighborhood_table,
    nta_name_lookup,
    reattach_correction,
    sanitize_manifest,
)
from opaque_housing.metrics.sale_filter import (
    SaleFilterConfig,
    apply_sale_filter,
    attach_primary_parties,
)
from opaque_housing.metrics.stock import headline_shares, private_residential, stock_breakdowns
from opaque_housing.opacity.build import attach_parcel_owners, run_opacity
from opaque_housing.opacity.tiers import OPACITY_VERSION
from opaque_housing.paths import derived_dir, latest_raw_file, published_dir, raw_dir
from opaque_housing.quality.manifest import RunManifest
from opaque_housing.resolve.cluster import component_sizes
from opaque_housing.resolve.denylist import ADDRESS_DEGREE_THRESHOLD, seed_agent_names
from opaque_housing.schema import ENTITY_OWNED_CLASSES, BuildingType, OwnerClass

_AGENT_LOOKUP = Path(__file__).parent / "adapters/nyc/lookups/nys_dos_agent_names.csv"

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
    day = date.fromisoformat(retrieval_date) if retrieval_date else date.today()
    if metro == "phl":
        try:
            carto_specs = resolve_phl_specs(dataset)
        except KeyError:
            typer.echo(f"unknown dataset {dataset}", err=True)
            raise typer.Exit(code=1) from None
        for spec in carto_specs:
            dest = raw_dir(metro, spec.name, day) / spec.filename
            if dest.exists() and not force:
                typer.echo(f"skip existing {dest}")
                continue
            typer.echo(f"downloading {spec.table} -> {dest}")
            write_carto_csv(dest, spec)
            typer.echo(f"wrote {dest} ({dest.stat().st_size} bytes)")
        return
    if metro != "nyc":
        typer.echo(f"ingest is only wired for nyc and phl (got {metro})", err=True)
        raise typer.Exit(code=1)
    try:
        specs = resolve_ingest_specs(dataset)
    except KeyError:
        typer.echo(f"unknown dataset {dataset}", err=True)
        raise typer.Exit(code=1) from None
    for spec in specs:
        dest = raw_dir(metro, spec.name, day) / spec.filename
        if dest.exists() and not force:
            typer.echo(f"skip existing {dest}")
            continue
        typer.echo(f"downloading {spec.dataset_id} -> {dest}")
        if spec.paged:
            stats = write_soda_parquet(
                dest,
                spec.dataset_id,
                select=spec.select,
                where=spec.where,
                key=spec.key,
                page_size=spec.limit,
                host=spec.host,
            )
            typer.echo(
                f"wrote {dest} pages={stats['pages']} rows={stats['rows']} "
                f"({dest.stat().st_size} bytes)"
            )
        else:
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
        str | None, typer.Option(help="Canonical snapshot date. Default depends on metro.")
    ] = None,
    gold: Annotated[
        Path | None,
        typer.Option(help="Optional labeled gold CSV for Rogan–Gladen correction."),
    ] = None,
) -> None:
    """Classify residential parcels and write stock shares."""
    dest = out_dir or derived_dir(metro)
    dest.mkdir(parents=True, exist_ok=True)
    started = datetime.now(tz=UTC)
    if metro == "phl":
        source_path = source or latest_raw_file(metro, "opa", "opa_properties_public.csv")
        if source_path is None or not source_path.exists():
            typer.echo("no OPA extract; pass --source or run oh ingest --metro phl", err=True)
            raise typer.Exit(code=1)
        snap = date.fromisoformat(snapshot_date or OPA_SNAPSHOT_DATE)
        adapter = PhlOpaAdapter(snapshot_date=snap)
        parcels = adapter.load_parcels_snapshot(source_path)
        source_label = "opa"
        extra_paths = {}
        equiv_path = None
    elif metro == "nyc":
        source_path = source or latest_raw_file(metro, "pluto", NYC_SOURCES["pluto"].filename)
        if source_path is None or not source_path.exists():
            typer.echo("no PLUTO extract; pass --source or run oh ingest", err=True)
            raise typer.Exit(code=1)
        equiv_path = equiv or latest_raw_file(metro, "tract_nta", NYC_SOURCES["tract_nta"].filename)
        snap = date.fromisoformat(snapshot_date or PLUTO_SNAPSHOT_DATE)
        adapter = NycPlutoAdapter(snapshot_date=snap, tract_equiv_path=equiv_path)
        parcels = adapter.load_parcels_snapshot(source_path)
        source_label = "pluto"
        extra_paths = {"tract_nta": str(equiv_path) if equiv_path else ""}
    else:
        typer.echo(f"build is only wired for nyc and phl (got {metro})", err=True)
        raise typer.Exit(code=1)
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
    neighborhood_concentration(private).write_csv(dest / "concentration_by_neighborhood.csv")
    (dest / "headlines.json").write_text(json.dumps(headlines, indent=2) + "\n")

    versions = sorted(classified["source_version"].drop_nulls().unique().to_list())
    manifest = RunManifest(
        metro_id=metro,
        started_at=started.isoformat(),
        finished_at=datetime.now(tz=UTC).isoformat(),
        source_paths={source_label: str(source_path), **extra_paths},
        source_versions={source_label: ",".join(versions)},
        rules_version=RULES_VERSION,
        filter_counts=[*adapter.filter_counts, private_count],
        notes=[
            "raw shares only" if correction is None else "raw shares plus gold-set correction",
            "trusts are not in the entity headline",
        ],
    )
    (dest / "run_manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2) + "\n")
    typer.echo(f"wrote {dest} parcels={classified.height} private={private.height}")


@app.command()
def flow(
    metro: Annotated[str, typer.Option(help="Metro id, e.g. nyc.")] = "nyc",
    master: Annotated[Path | None, typer.Option(help="ACRIS Master extract.")] = None,
    legals: Annotated[Path | None, typer.Option(help="ACRIS Legals extract.")] = None,
    parties: Annotated[Path | None, typer.Option(help="ACRIS Parties extract.")] = None,
    parcels: Annotated[
        Path | None, typer.Option(help="Classified parcels parquet from oh build.")
    ] = None,
    rtt: Annotated[Path | None, typer.Option(help="Philadelphia RTT extract.")] = None,
    pad: Annotated[Path | None, typer.Option(help="Optional PAD BBL crosswalk.")] = None,
    out_dir: Annotated[Path | None, typer.Option(help="Derived output directory.")] = None,
    min_consideration: Annotated[float, typer.Option(help="Arm's-length amount cut.")] = 10_000.0,
    snapshot_date: Annotated[
        str | None, typer.Option(help="As-of date for the current-stock consistency check.")
    ] = None,
) -> None:
    """Entity-buyer flow, reconstructed history, and current-stock consistency."""
    dest = out_dir or derived_dir(metro)
    dest.mkdir(parents=True, exist_ok=True)
    started = datetime.now(tz=UTC)
    parcel_path = parcels or (derived_dir(metro) / "parcels_classified.parquet")
    pad_frame = load_pad_crosswalk(pad) if pad is not None else None
    if metro == "phl":
        rtt_path = rtt or latest_raw_file(metro, "rtt", "rtt_summary.csv")
        if rtt_path is None or not rtt_path.exists() or not parcel_path.exists():
            typer.echo("missing PHL inputs; pass --rtt and run oh build --metro phl", err=True)
            raise typer.Exit(code=1)
        adapter = PhlRttAdapter()
        typer.echo("loading RTT_SUMMARY")
        transfers = adapter.load_transfers(rtt_path)
        typer.echo(f"transfers={transfers.height}")
        source_paths = {"rtt": str(rtt_path), "parcels": str(parcel_path)}
        source_versions = {"rtt": adapter.source_version, "rules": RULES_VERSION}
        window = COVERAGE_WINDOWS["phl"]
        snap = date.fromisoformat(snapshot_date or OPA_SNAPSHOT_DATE)
        sensitivity_configs = PHL_SENSITIVITY_CONFIGS
        window_note = "coverage window recorded years 2000-2025 (ADR 0010)"
    elif metro == "nyc":
        master_path = master or latest_raw_file(
            metro, "acris_master", ACRIS_SOURCES["acris_master"].filename
        )
        legals_path = legals or latest_raw_file(
            metro, "acris_legals", ACRIS_SOURCES["acris_legals"].filename
        )
        parties_path = parties or latest_raw_file(
            metro, "acris_parties", ACRIS_SOURCES["acris_parties"].filename
        )
        missing = [
            label
            for label, path in (
                ("master", master_path),
                ("legals", legals_path),
                ("parties", parties_path),
                ("parcels", parcel_path),
            )
            if path is None or not path.exists()
        ]
        if missing:
            typer.echo(f"missing inputs: {', '.join(missing)}", err=True)
            raise typer.Exit(code=1)
        assert master_path is not None and legals_path is not None and parties_path is not None
        adapter = NycAcrisAdapter()
        typer.echo("loading ACRIS master/legals/parties")
        transfers = adapter.load_transfers(master_path, legals_path)
        party_rows = adapter.load_transfer_parties(parties_path)
        transfers = attach_primary_parties(transfers, party_rows)
        typer.echo(f"transfers={transfers.height} parties={party_rows.height}")
        source_paths = {
            "acris_master": str(master_path),
            "acris_legals": str(legals_path),
            "acris_parties": str(parties_path),
            "parcels": str(parcel_path),
            "pad": str(pad) if pad else "",
        }
        source_versions = {"acris": adapter.source_version, "rules": RULES_VERSION}
        window = COVERAGE_WINDOWS["nyc"]
        snap = date.fromisoformat(snapshot_date or PLUTO_SNAPSHOT_DATE)
        sensitivity_configs = None
        window_note = "coverage window recorded years 2003-2025 (ADR 0006)"
    else:
        typer.echo(f"flow is only wired for nyc and phl (got {metro})", err=True)
        raise typer.Exit(code=1)
    parcel_frame = pl.read_parquet(parcel_path)

    hist_sales, hist_counts = history_only_sales(transfers)
    typer.echo(f"classifying {hist_sales.height} named sale-deed buyers")
    hist_buyers = classify_buyers(hist_sales)
    flow_sales, flow_counts = apply_sale_filter(
        hist_buyers, SaleFilterConfig(min_consideration=min_consideration)
    )
    flow_matched, join_counts = attach_residential(flow_sales, parcel_frame, pad_frame)
    flow_matched = with_year_and_borough(flow_matched)
    flow_matched, window_count = in_coverage_window(flow_matched, window[0], window[1])
    breakdowns = flow_breakdowns(flow_matched)
    headlines = flow_headlines(flow_matched, window[0], window[1])
    typer.echo("sensitivity table")
    sensitivity = sensitivity_table(
        hist_buyers,
        parcel_frame,
        pad_frame,
        configs=sensitivity_configs,
        start=window[0],
        end=window[1],
    )

    hist_matched, hist_join = attach_residential(hist_buyers, parcel_frame, pad_frame)
    hist_matched = with_year_and_borough(hist_matched)
    history = historical_stock_table(
        hist_matched, parcel_frame, year_end_dates(window[0], window[1])
    )
    consistency = consistency_check(hist_matched, parcel_frame, snap)

    for name, table in breakdowns.items():
        table.write_csv(dest / f"flow_{name}.csv")
    sensitivity.write_csv(dest / "flow_sensitivity.csv")
    history.write_csv(dest / "history_by_year.csv")
    (dest / "flow_headlines.json").write_text(json.dumps(headlines, indent=2) + "\n")
    (dest / "consistency.json").write_text(json.dumps(consistency, indent=2) + "\n")

    manifest = RunManifest(
        metro_id=metro,
        started_at=started.isoformat(),
        finished_at=datetime.now(tz=UTC).isoformat(),
        source_paths=source_paths,
        source_versions=source_versions,
        rules_version=RULES_VERSION,
        filter_counts=[
            *adapter.filter_counts,
            *flow_counts,
            *join_counts,
            window_count,
            *hist_counts,
            *hist_join,
        ],
        notes=[
            "flow uses sale_deed + named grantee + consideration cut (ADR 0005)",
            "history uses every sale_deed with a named grantee",
            window_note,
            "trusts are not in the entity headline",
        ],
    )
    (dest / "flow_manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2) + "\n")
    typer.echo(
        f"wrote {dest} flow_sales={headlines['private_residential']['sales']} "
        f"entity_share={headlines['private_residential']['sale_share']:.4f}"
    )


@app.command()
def opacity(
    metro: Annotated[str, typer.Option(help="Metro id, e.g. nyc.")] = "nyc",
    parcels: Annotated[
        Path | None, typer.Option(help="Classified parcels parquet from oh build.")
    ] = None,
    registrations: Annotated[Path | None, typer.Option(help="HPD registrations extract.")] = None,
    contacts: Annotated[Path | None, typer.Option(help="HPD contacts extract.")] = None,
    dos: Annotated[Path | None, typer.Option(help="NY DOS active-corporations extract.")] = None,
    out_dir: Annotated[Path | None, typer.Option(help="Derived output directory.")] = None,
    review_out: Annotated[Path, typer.Option(help="Top-20 cluster review markdown.")] = Path(
        "eval/reports/cluster_review_top20.md"
    ),
    address_degree: Annotated[int, typer.Option(help="Deny addresses at this owner degree.")] = (
        ADDRESS_DEGREE_THRESHOLD
    ),
) -> None:
    """Assign opacity tiers, cluster portfolios, and write internal shares."""
    if metro != "nyc":
        typer.echo(f"opacity is only wired for nyc (got {metro})", err=True)
        raise typer.Exit(code=1)
    parcel_path = parcels or (derived_dir(metro) / "parcels_classified.parquet")
    regs_path = registrations or latest_raw_file(
        metro, "hpd_registrations", HPD_SOURCES["hpd_registrations"].filename
    )
    contacts_path = contacts or latest_raw_file(
        metro, "hpd_contacts", HPD_SOURCES["hpd_contacts"].filename
    )
    dos_path = dos or latest_raw_file(metro, "nys_dos", NYS_DOS.filename)
    missing = [
        label
        for label, path in (
            ("parcels", parcel_path),
            ("hpd_registrations", regs_path),
            ("hpd_contacts", contacts_path),
            ("nys_dos", dos_path),
        )
        if path is None or not path.exists()
    ]
    if missing:
        typer.echo(f"missing inputs: {', '.join(missing)}", err=True)
        raise typer.Exit(code=1)
    assert regs_path is not None and contacts_path is not None and dos_path is not None
    dest = out_dir or derived_dir(metro)
    dest.mkdir(parents=True, exist_ok=True)
    started = datetime.now(tz=UTC)

    parcel_frame = pl.read_parquet(parcel_path)
    hpd = NycHpdAdapter()
    dos_adapter = NycDosAdapter()
    typer.echo("loading HPD registrations and contacts")
    latest = hpd.latest_registration_per_parcel(hpd.load_registrations(regs_path))
    hpd_contacts = hpd.contacts_on_latest(hpd.load_contacts(contacts_path), latest)
    hpd_on_parcels = attach_parcel_owners(hpd_contacts, parcel_frame)
    typer.echo(f"hpd contacts on parcels={hpd_on_parcels.height}")
    seeds = seed_agent_names(pl.read_csv(_AGENT_LOOKUP)["name_raw"].to_list())
    owner_keys = (
        parcel_frame.filter(pl.col("owner_class").is_in(list(_ENTITY_VALUES)))
        .select("owner_key")
        .unique()
    )
    typer.echo(f"matching NY DOS to {owner_keys.height} entity owner keys")
    dos_matched = dos_adapter.load_entities(dos_path, owner_keys=owner_keys)
    typer.echo(f"dos matched={dos_matched.height}")
    results, links, denied, membership = run_opacity(
        parcel_frame,
        hpd_on_parcels,
        dos_matched,
        seeds=seeds,
        threshold=address_degree,
    )
    with_tiers = attach_clusters(attach_opacity(parcel_frame, results), membership)
    private, private_count = private_residential(with_tiers)
    entity_rows, entity_count = entity_owned(private)
    headlines = opacity_headlines(with_tiers)
    by_type = opacity_by_type(with_tiers)
    keep = set(entity_rows["owner_key"].to_list()) if entity_rows.height else set()
    sizes = component_sizes(membership, keep=keep)
    headlines["clusters"] = {
        "entity_owners": len(keep),
        "components": len(sizes),
        "largest_owners": max(sizes.values()) if sizes else 0,
        "large_components": sum(1 for count in sizes.values() if count >= 200),
        "dos_matched": dos_matched.height,
        "dos_owner_keys": owner_keys.height,
    }
    review = top_cluster_review(entity_rows)
    review_out.parent.mkdir(parents=True, exist_ok=True)
    review_out.write_text(_cluster_review_markdown(review, sizes) + "\n")

    with_tiers.write_parquet(dest / "parcels_opacity.parquet")
    links.write_csv(dest / "owner_links.csv")
    denied.write_csv(dest / "denied_addresses.csv")
    by_type.write_csv(dest / "opacity_by_type.csv")
    (dest / "opacity_headlines.json").write_text(json.dumps(headlines, indent=2) + "\n")
    (dest / "opacity_results.json").write_text(
        json.dumps(
            [
                {
                    "owner_key": row.owner_key,
                    "tier": row.tier.value,
                    "rule_id": row.rule_id,
                    "evidence": row.evidence,
                    "rules_version": row.rules_version,
                }
                for row in results
            ]
        )
        + "\n"
    )
    manifest = RunManifest(
        metro_id=metro,
        started_at=started.isoformat(),
        finished_at=datetime.now(tz=UTC).isoformat(),
        source_paths={
            "parcels": str(parcel_path),
            "hpd_registrations": str(regs_path),
            "hpd_contacts": str(contacts_path),
            "nys_dos": str(dos_path),
        },
        source_versions={
            "hpd": hpd.source_version,
            "nys_dos": dos_adapter.source_version,
            "opacity": OPACITY_VERSION,
        },
        rules_version=RULES_VERSION,
        filter_counts=[*hpd.filter_counts, *dos_adapter.filter_counts, private_count, entity_count],
        notes=[
            "O-tiers on entity-owned private residential lots only (ADR 0007)",
            f"address degree threshold {address_degree} (ADR 0008)",
            "cluster review lists entity names only",
        ],
    )
    (dest / "opacity_manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2) + "\n")
    entity_block = headlines["entity_owned"]
    typer.echo(
        f"wrote {dest} entity_parcels={entity_block['parcels']} "
        f"o1_unit={entity_block['by_tier']['O1']['unit_share']}"
    )


@app.command("eval")
def eval_cmd(
    gold: Annotated[Path, typer.Option(help="Labeled gold CSV.")] = Path("eval/gold/ci_dev.csv"),
    baseline: Annotated[Path, typer.Option(help="Stored macro-F1 baseline.")] = Path(
        "eval/reports/baseline_macro_f1.json"
    ),
    split: Annotated[str, typer.Option(help="dev, test, or all.")] = "test",
    out: Annotated[Path, typer.Option(help="Report JSON.")] = Path("eval/reports/rules_eval.json"),
    with_llm: Annotated[bool, typer.Option(help="Also score rules+LLM on R999 names.")] = False,
    llm_cache: Annotated[Path, typer.Option(help="DuckDB LLM cache.")] = Path(
        "data/derived/nyc/llm_cache.duckdb"
    ),
    llm_cost_cap: Annotated[float, typer.Option(help="Abort live LLM calls above this USD.")] = 5.0,
    llm_max_names: Annotated[int, typer.Option(help="Max live LLM names this run.")] = 500,
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
    report["source"] = "rules"
    if with_llm:
        llm_pred, llm_meta = _predict_with_llm(
            rows, cache_path=llm_cache, cost_cap=llm_cost_cap, max_names=llm_max_names
        )
        llm_report = evaluation_report(y_true, llm_pred)
        llm_macro = llm_report["macro_f1"]
        rules_macro = report["macro_f1"]
        if not isinstance(llm_macro, float) or not isinstance(rules_macro, float):
            raise TypeError("macro_f1 must be float")
        report["llm"] = {
            **llm_report,
            "prompt_version": llm_meta["prompt_version"],
            "model_id": llm_meta["model_id"],
            "names_sent": llm_meta["names_sent"],
            "cache_hits": llm_meta["cache_hits"],
            "skipped": llm_meta["skipped"],
            "macro_f1_lift": llm_macro - rules_macro,
        }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    macro_f1_value = report["macro_f1"]
    if not isinstance(macro_f1_value, float):
        raise TypeError("macro_f1 must be float")
    typer.echo(f"macro_f1={macro_f1_value:.4f} n={report['n']} -> {out}")
    llm_block = report.get("llm")
    if with_llm and isinstance(llm_block, dict):
        llm_f1 = llm_block["macro_f1"]
        lift = llm_block["macro_f1_lift"]
        sent = llm_block["names_sent"]
        if not isinstance(llm_f1, float) or not isinstance(lift, float):
            raise TypeError("llm macro_f1 must be float")
        typer.echo(f"rules+llm macro_f1={llm_f1:.4f} lift={lift:.4f} sent={sent}")
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
def publish(
    metro: Annotated[str, typer.Option(help="Metro id, e.g. nyc.")] = "nyc",
    derived: Annotated[Path | None, typer.Option(help="Derived directory from build/flow.")] = None,
    out_dir: Annotated[Path | None, typer.Option(help="Public aggregate directory.")] = None,
    site_data: Annotated[
        Path | None, typer.Option(help="Optional copy of public files for the static site.")
    ] = Path("site/data"),
    reuse_dir: Annotated[
        Path | None,
        typer.Option(help="Prior published dir for flow/opacity reuse. Default: --out-dir."),
    ] = None,
    equiv: Annotated[Path | None, typer.Option(help="Tract-NTA equivalency CSV.")] = None,
    max_stock_change: Annotated[
        float, typer.Option(help="Fail if private parcel count moves more than this.")
    ] = 0.20,
) -> None:
    """Copy allowlisted aggregates. Never writes names, addresses, or owner keys."""
    if metro not in {"nyc", "phl"}:
        typer.echo(f"publish is only wired for nyc and phl (got {metro})", err=True)
        raise typer.Exit(code=1)
    src = derived or derived_dir(metro)
    dest = out_dir or published_dir(metro)
    prior = reuse_dir or dest
    site_dest = site_data
    if metro != "nyc" and site_data == Path("site/data"):
        site_dest = Path("site/data") / metro
    try:
        _publish_aggregates(
            metro=metro,
            derived=src,
            dest=dest,
            prior=prior,
            site_data=site_dest,
            equiv=equiv or latest_raw_file(metro, "tract_nta", NYC_SOURCES["tract_nta"].filename),
            max_stock_change=max_stock_change,
        )
    except PublishError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"wrote {dest}")


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port.")] = 8000,
    published: Annotated[
        Path | None, typer.Option(help="Allowlisted published-aggregate root.")
    ] = None,
) -> None:
    """Serve the insight app over published aggregates only."""
    import os

    import uvicorn

    from opaque_housing.app.main import create_app

    bind_port = port if port != 8000 else int(os.environ.get("PORT", "8000"))
    uvicorn.run(create_app(published_root=published), host=host, port=bind_port)


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


def _predict_with_llm(
    rows: list[dict[str, str]],
    *,
    cache_path: Path,
    cost_cap: float,
    max_names: int,
) -> tuple[list[str], dict[str, object]]:
    from opaque_housing.adapters.llm_cache import LlmCache
    from opaque_housing.classify.llm import PROMPT_VERSION

    cache = LlmCache(cache_path)
    model_id = ""
    client = None
    try:
        from opaque_housing.adapters.anthropic import AnthropicClassifier

        client = AnthropicClassifier(cost_cap_usd=cost_cap, max_names=max_names)
        model_id = client.model
    except RuntimeError:
        client = None
    names_sent = 0
    cache_hits = 0
    skipped = 0
    preds: list[str] = []
    try:
        for row in rows:
            parsed = BuildingType(row["building_type"]) if row.get("building_type") else None
            owner = classify_owner(row["name_raw"], parsed)
            if not needs_llm(owner):
                preds.append(owner.owner_class.value)
                continue
            label = cache.get(owner.owner_key, model_id or "cache-only") if model_id else None
            if label is None and model_id:
                # try any cached row for this owner_key+prompt by reading with the live model
                label = cache.get(owner.owner_key, model_id)
            if label is None and not model_id:
                # cache-only: look up with empty model skipped
                skipped += 1
                preds.append(owner.owner_class.value)
                continue
            if label is None and client is not None:
                try:
                    label = client.classify_name(owner.name_normalized)
                    cache.put(owner.owner_key, owner.name_normalized, label)
                    names_sent += 1
                except Exception as exc:  # noqa: BLE001
                    skipped += 1
                    typer.echo(f"llm skipped {owner.name_normalized}: {exc}", err=True)
                    preds.append(owner.owner_class.value)
                    continue
            elif label is not None:
                cache_hits += 1
            preds.append(apply_llm_label(owner, label).owner_class.value)
    finally:
        cache.close()
    return preds, {
        "prompt_version": PROMPT_VERSION,
        "model_id": model_id,
        "names_sent": names_sent,
        "cache_hits": cache_hits,
        "skipped": skipped,
    }


def _cluster_review_markdown(
    review: list[dict[str, object]],
    sizes: dict[str, int],
) -> str:
    lines = [
        "# Top-20 portfolio cluster review",
        "",
        f"Opacity rules `{OPACITY_VERSION}`. Entity names only; HPD person names are omitted.",
        "",
        f"Components (PLUTO entity owners): {len(sizes)}. "
        f"Largest owner-count: {max(sizes.values()) if sizes else 0}.",
        "",
    ]
    if not review:
        lines.append("No clusters to review.")
        return "\n".join(lines)
    for index, row in enumerate(review, start=1):
        names_raw = row["entity_names"]
        names = ", ".join(str(name) for name in names_raw) if isinstance(names_raw, list) else ""
        flag = f" **{row['flag']}**" if row.get("flag") else ""
        lines.extend(
            [
                f"## {index}. cluster `{row['cluster_id']}`{flag}",
                "",
                f"- parcels: {row['parcels']}; units: {row['units']}; "
                f"entity owners: {row['owners']}; O1 parcels: {row['o1_parcels']}",
                f"- entity names: {names}",
                "",
            ]
        )
    return "\n".join(lines)


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


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise PublishError(f"{path} is not a JSON object")
    return payload


def _optional_csv(path: Path | None) -> pl.DataFrame | None:
    if path is None or not path.exists():
        return None
    table = pl.read_csv(path, infer_schema_length=0)
    assert_safe_columns(table.columns, origin=path.name)
    return table


def _resolve_publish_file(name: str, derived: Path, prior: Path) -> tuple[Path | None, str]:
    assert_allowed_filename(name)
    current = derived / name
    if current.exists():
        return current, "derived"
    reused = prior / name
    if reused.exists():
        return reused, "reused"
    return None, "missing"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _publish_aggregates(
    *,
    metro: str,
    derived: Path,
    dest: Path,
    prior: Path,
    site_data: Path | None,
    equiv: Path | None,
    max_stock_change: float,
) -> None:
    for name in FORBIDDEN_FILENAMES:
        if (dest / name).exists():
            raise PublishError(f"{dest / name} must not be published")
    origins: dict[str, str] = {}
    resolved: dict[str, Path] = {}
    for name in sorted(ALLOWED_FILES):
        path, origin = _resolve_publish_file(name, derived, prior)
        if path is None:
            if name in REQUIRED_FILES:
                raise PublishError(f"missing required aggregate {name}")
            continue
        origins[name] = origin
        resolved[name] = path

    headlines = _read_json(resolved["headlines.json"])
    prior_headlines: dict[str, object] | None = None
    prior_head_path = prior / "headlines.json"
    current_head = resolved["headlines.json"].resolve()
    if prior_head_path.exists() and prior_head_path.resolve() != current_head:
        prior_headlines = _read_json(prior_head_path)
    headlines = reattach_correction(headlines, prior_headlines)

    private = headlines.get("private_all_entity_only")
    current_parcels = 0
    if isinstance(private, dict) and "parcels" in private:
        current_parcels = int(private["parcels"])
    previous_parcels = None
    if prior_headlines:
        prior_private = prior_headlines.get("private_all_entity_only")
        if isinstance(prior_private, dict) and "parcels" in prior_private:
            previous_parcels = int(prior_private["parcels"])
    assert_stock_stable(previous_parcels, current_parcels, max_change=max_stock_change)

    nta_type = pl.read_csv(resolved["stock_by_nta_type.csv"], infer_schema_length=0)
    assert_safe_columns(nta_type.columns, origin="stock_by_nta_type.csv")
    names = None
    if equiv is not None and equiv.exists():
        names = nta_name_lookup(pl.read_csv(equiv, infer_schema_length=0))
        assert_safe_columns(names.columns, origin="nta_names")
    neighborhoods = neighborhood_table(nta_type, names)
    if metro == "phl":
        neighborhoods = neighborhoods.with_columns(
            pl.lit("Philadelphia").alias("borough"),
            pl.col("nta").alias("nta_name"),
        )
    boroughs = None
    borough_path = resolved.get("stock_by_borough_type.csv")
    if borough_path is not None:
        boroughs = borough_table(pl.read_csv(borough_path, infer_schema_length=0))

    dest.mkdir(parents=True, exist_ok=True)
    for name, path in resolved.items():
        target = dest / name
        if name.endswith(".json"):
            payload = _read_json(path)
            if name.endswith("_manifest.json") or name == "run_manifest.json":
                payload = sanitize_manifest(payload)
            if name == "headlines.json":
                payload = headlines
            _write_json(target, payload)
        else:
            table = pl.read_csv(path, infer_schema_length=0)
            assert_safe_columns(table.columns, origin=name)
            table.write_csv(target)

    neighborhoods.write_csv(dest / "neighborhoods.csv")
    if names is not None:
        names.write_csv(dest / "nta_names.csv")

    flow_hl = (
        _read_json(resolved["flow_headlines.json"]) if "flow_headlines.json" in resolved else None
    )
    opacity_hl = (
        _read_json(resolved["opacity_headlines.json"])
        if "opacity_headlines.json" in resolved
        else None
    )
    consistency = (
        _read_json(resolved["consistency.json"]) if "consistency.json" in resolved else None
    )
    run_manifest = (
        sanitize_manifest(_read_json(resolved["run_manifest.json"]))
        if ("run_manifest.json" in resolved)
        else {}
    )
    freshness = {
        "metro": metro,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "stock": run_manifest,
        "reused": {name: origin for name, origin in origins.items() if origin == "reused"},
        "flow_present": "flow_headlines.json" in resolved,
        "opacity_present": "opacity_headlines.json" in resolved,
        "notes": [
            "GitHub-hosted refresh updates NYC PLUTO stock and PHL OPA stock (ADR 0011).",
            "ACRIS, NY DOS, and PHL RTT stay laptop-only; "
            "flow and opacity are reused when missing.",
        ],
    }
    _write_json(dest / "freshness.json", freshness)
    sensitivity = stock_sensitivity_table(headlines)
    assert_safe_columns(sensitivity.columns, origin="stock_sensitivity.csv")
    sensitivity.write_csv(dest / "stock_sensitivity.csv")
    concentration = _optional_csv(resolved.get("concentration_by_neighborhood.csv"))
    payload = assemble_site_payload(
        metro=metro,
        generated_at=str(freshness["generated_at"]),
        headlines=headlines,
        neighborhoods=neighborhoods,
        boroughs=boroughs,
        stock_by_class=_optional_csv(resolved.get("stock_by_class.csv")),
        stock_by_type=_optional_csv(resolved.get("stock_by_building_type.csv")),
        flow_headlines=flow_hl,
        flow_by_year=_optional_csv(resolved.get("flow_by_year.csv")),
        flow_sfr_condo=_optional_csv(resolved.get("flow_sfr_condo_by_year.csv")),
        flow_sensitivity=_optional_csv(resolved.get("flow_sensitivity.csv")),
        history_by_year=_optional_csv(resolved.get("history_by_year.csv")),
        consistency=consistency,
        opacity_headlines=opacity_hl,
        opacity_by_type=_optional_csv(resolved.get("opacity_by_type.csv")),
        freshness=freshness,
        reused={name: origin for name, origin in origins.items() if origin == "reused"},
        concentration=concentration,
        stock_sensitivity=sensitivity,
    )
    _write_json(dest / "site.json", payload)
    _write_json(
        dest / "publish_manifest.json",
        {"metro": metro, "origins": origins, "files": sorted(p.name for p in dest.iterdir())},
    )

    for path in dest.iterdir():
        if path.name in FORBIDDEN_FILENAMES:
            raise PublishError(f"refusing to leave {path.name} in {dest}")
        if path.suffix == ".csv":
            assert_safe_columns(pl.read_csv(path, n_rows=0).columns, origin=path.name)
        elif path.suffix == ".json":
            dumped = json.loads(path.read_text())
            if isinstance(dumped, dict):
                assert_safe_columns(list(dumped.keys()), origin=path.name)

    if site_data is not None:
        site_data.mkdir(parents=True, exist_ok=True)
        for path in dest.iterdir():
            target = site_data / path.name
            target.write_bytes(path.read_bytes())
