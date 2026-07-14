from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from emd.cli._app import app
from emd.cli._pipeline import (
    ensure_file,
    ensure_target,
    load_step,
    prepare_df,
    run_analyzers,
    split_csv_option,
)
from emd.cli._ui import BAND_COLORS, Steps, console, err_console, header, output_panel

# Warnings/Information are capped in the terminal (full lists go to doctor-report.md);
# Critical Issues are always shown in full.
_DOCTOR_MAX_TERMINAL_ITEMS = 5


def _score_detail(band: str, score: int) -> str:
    color = BAND_COLORS.get(band, "white")
    return f"[{color}]{score} / 100[/{color}]"


def _doctor_section(title: str, findings: list[Any], bullet: str, cap: int | None) -> None:
    console.print(f"[bold]{title} ({len(findings)})[/bold]")
    if not findings:
        console.print("  [dim]None detected.[/dim]")
    else:
        shown = findings if cap is None else findings[:cap]
        for finding in shown:
            console.print(f"  {bullet} {finding.message}")
        hidden = len(findings) - len(shown)
        if hidden > 0:
            console.print(f"  [dim]… +{hidden} more in doctor-report.md[/dim]")
    console.print()


def _render_doctor(result: Any) -> None:
    """Prints the six doctor sections (Output panel is printed by the caller)."""
    from emd.analysis import DoctorSeverity

    band_color = BAND_COLORS.get(result.band, "white")
    console.print()
    console.print("[bold]Dataset Health Score[/bold]")
    console.print(f"  [bold {band_color}]{result.score} / 100 — {result.band}[/bold {band_color}]")
    console.print()
    console.print("[bold]Overall Assessment[/bold]")
    console.print(f"  {result.assessment}")
    console.print()
    _doctor_section(
        "Critical Issues", result.by_severity(DoctorSeverity.CRITICAL), "[red]✗[/red]", cap=None,
    )
    _doctor_section(
        "Warnings", result.by_severity(DoctorSeverity.WARNING), "[yellow]![/yellow]",
        cap=_DOCTOR_MAX_TERMINAL_ITEMS,
    )
    _doctor_section(
        "Information", result.by_severity(DoctorSeverity.INFO), "[blue]·[/blue]",
        cap=_DOCTOR_MAX_TERMINAL_ITEMS,
    )


@app.command()
def doctor(
    file: Annotated[Path, typer.Argument(help="Path to CSV or XLSX file")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output directory")
    ] = Path("./reports"),
    target: Annotated[
        str | None,
        typer.Option("--target", help="Target column — enables leakage and imbalance checks"),
    ] = None,
    sheet: Annotated[str | None, typer.Option("--sheet", help="XLSX sheet name")] = None,
    drop_cols: Annotated[
        str, typer.Option("--drop-cols", help="Comma-separated columns to drop")
    ] = "",
    sample: Annotated[int | None, typer.Option("--sample", help="Random sample size")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress terminal output")] = False,
) -> None:
    """Audit a dataset for practical issues to review before modeling.

    Answers "what could be wrong with this dataset?" — a deterministic health
    score plus findings grouped by severity. Diagnostics only: no statistics,
    no charts, no advice. Writes doctor-report.md with the full finding list.
    Exits 1 on a bad or empty file.
    Example: emd doctor data.csv --target SalePrice
    """
    from emd.analysis import DoctorAnalyzer
    from emd.quality import QualityChecker, Severity
    from emd.report import MarkdownReportGenerator

    ensure_file(file)

    if not quiet:
        header("doctor", file.name)

    with Steps(quiet) as steps:
        df = load_step(steps, file, sheet)
        df = prepare_df(df, split_csv_option(drop_cols), sample, quiet)

        # No quality gate: diagnosing broken data is the whole point of doctor.
        # Only a dataset with nothing to diagnose (0 rows or 0 columns) aborts.
        quality_report = QualityChecker().check(df, no_quality_gate=True)
        if not quality_report.passed:
            steps.stop()
            fatal = next(i for i in quality_report.issues if i.severity == Severity.FATAL)
            err_console.print(f"[red]Cannot diagnose {file.name}:[/red] {fatal.result}")
            raise typer.Exit(1)

        ensure_target(steps, df, target)

        results = steps.run(
            "Analyze data", lambda: run_analyzers(df, target=target),
        )

        doctor_result = steps.run(
            "Run diagnostics",
            lambda: DoctorAnalyzer().diagnose(
                df,
                dist_result=results["dist"],
                missing_result=results["missing"],
                corr_result=results["corr"],
                outlier_result=results["outlier"],
                quality_report=quality_report,
                target_result=results.get("target"),
            ),
            detail=lambda r: _score_detail(r.band, r.score),
        )

        out_dir = Path(output) / file.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = steps.run(
            "Write report",
            lambda: MarkdownReportGenerator().generate_doctor_report(
                df=df, result=doctor_result, output_dir=out_dir, source_name=file.name,
            ),
        )

    if quiet:
        return

    _render_doctor(doctor_result)
    output_panel({"Report": str(report_path)})
