"""Typer app assembly. Command modules import `app`/`schema_app` and register onto them."""
from __future__ import annotations

from typing import Annotated

import typer

from emd import __version__
from emd.cli._ui import console

app = typer.Typer(
    name="emd",
    help="Explain My Data — automated EDA reports from CSV/XLSX files.",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)
schema_app = typer.Typer(name="schema", help="Schema contract generation and validation.")
app.add_typer(schema_app)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"emd version [cyan]{__version__}[/cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Show the version and exit"
        ),
    ] = None,
) -> None:
    """Explain My Data — automated EDA reports from CSV/XLSX files."""
