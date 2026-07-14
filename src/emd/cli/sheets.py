from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from emd.cli._app import app
from emd.cli._pipeline import ensure_file
from emd.cli._ui import console, err_console, header


@app.command()
def sheets(
    file: Annotated[Path, typer.Argument(help="XLSX file to inspect")],
) -> None:
    """List sheets in an Excel file."""
    from emd.loader import XLSXLoader

    ensure_file(file)

    header("sheets", file.name)

    try:
        with console.status("Reading workbook..."):
            sheet_names = XLSXLoader().list_sheets(file)
    except Exception as exc:
        err_console.print(f"[red]Could not read {file.name}:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print()
    for i, name in enumerate(sheet_names, 1):
        console.print(f"  [cyan]{i}.[/cyan] {name}")
