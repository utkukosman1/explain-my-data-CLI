from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from emd.cli._app import app
from emd.cli._pipeline import ensure_file, load_or_exit
from emd.cli._ui import SEVERITY_COLORS, STATUS_COLORS, console, header, make_table


@app.command()
def check(
    file: Annotated[Path, typer.Argument(help="CSV or XLSX file to quality-check")],
    sheet: Annotated[str | None, typer.Option("--sheet")] = None,
) -> None:
    """Run only the data quality gate and display results."""
    from emd.quality import QualityChecker

    ensure_file(file)

    header("check", file.name)

    with console.status("Loading data..."):
        df = load_or_exit(file, sheet)
        qr = QualityChecker().check(df, no_quality_gate=True)

    console.print(
        f"Shape: [bold]{df.shape[0]:,}[/bold] rows x [bold]{df.shape[1]}[/bold] columns\n"
    )

    if qr.issues:
        table = make_table("Check", "Severity", "Result", "Recommendation")
        for issue in qr.issues:
            color = SEVERITY_COLORS.get(issue.severity.value, "white")
            table.add_row(
                issue.check,
                f"[{color}]{issue.severity.value}[/{color}]",
                issue.result,
                issue.recommendation,
            )
        console.print(table)
    else:
        console.print("[green]No issues detected — data looks clean.[/green]")

    color = STATUS_COLORS.get(qr.status, "white")
    console.print(f"\n[bold {color}]Quality gate: {qr.status}[/bold {color}]")
