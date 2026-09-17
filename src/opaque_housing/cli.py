"""Typer CLI. Network and file access for the pipeline live here and in adapters."""

from typing import Annotated

import typer

from opaque_housing import __version__

app = typer.Typer(no_args_is_help=True, help="Opaque housing investigation pipeline.")


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def ingest(
    metro: Annotated[str, typer.Option(help="Metro id, e.g. nyc.")] = "nyc",
) -> None:
    """Download raw source data into data/raw/. Not wired in Milestone 0."""
    typer.echo(f"ingest is not implemented (metro={metro})", err=True)
    raise typer.Exit(code=1)


@app.command()
def build(
    metro: Annotated[str, typer.Option(help="Metro id, e.g. nyc.")] = "nyc",
) -> None:
    """Run the pipeline for a metro. Not wired in Milestone 0."""
    typer.echo(f"build is not implemented (metro={metro})", err=True)
    raise typer.Exit(code=1)


@app.command()
def eval() -> None:
    """Run the evaluation harness. Not wired in Milestone 0."""
    typer.echo("eval is not implemented", err=True)
    raise typer.Exit(code=1)


@app.command()
def publish() -> None:
    """Publish aggregate parquet/csv. Not wired in Milestone 0."""
    typer.echo("publish is not implemented", err=True)
    raise typer.Exit(code=1)


@app.command()
def label() -> None:
    """Interactive gold-set labeling. Implemented in Milestone 1."""
    typer.echo("label is not implemented", err=True)
    raise typer.Exit(code=1)
