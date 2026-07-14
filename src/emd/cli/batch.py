from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from emd.cli._app import app
from emd.cli._ui import console, err_console, header
from emd.cli.analyze import _analyze_impl


@app.command()
def batch(
    directory: Annotated[Path, typer.Argument(help="Directory containing CSV/XLSX files")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output directory")
    ] = Path("./reports"),
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress per-file progress output")
    ] = False,
) -> None:
    """Run analyze on every CSV/XLSX file in a directory. Exits 1 if any file fails.

    Example: emd batch ./data/
    """
    if not directory.is_dir():
        err_console.print(f"[red]Not a directory:[/red] {directory}")
        raise typer.Exit(1)

    files = sorted(list(directory.glob("*.csv")) + list(directory.glob("*.xlsx")))
    if not files:
        console.print("[yellow]No CSV/XLSX files found in directory.[/yellow]")
        return

    if not quiet:
        header("batch", f"{directory}  ·  {len(files)} files")

    succeeded = 0
    failed_files: list[str] = []
    for i, f in enumerate(files):
        if not quiet and i > 0:
            console.print()
        try:
            _analyze_impl(file=f, output=str(output), quiet=quiet)
            succeeded += 1
        except typer.Exit:
            failed_files.append(f.name)
        except Exception as exc:
            failed_files.append(f.name)
            err_console.print(f"[red]Failed:[/red] {f.name} — {exc}")

    if not quiet:
        summary_color = "red" if not succeeded else ("yellow" if failed_files else "green")
        console.print()
        console.print(
            f"[bold {summary_color}]Batch summary:[/bold {summary_color}] "
            f"{succeeded} succeeded, {len(failed_files)} failed"
        )
        for name in failed_files:
            console.print(f"  [red]✗[/red] {name}")

    if failed_files:
        raise typer.Exit(1)
