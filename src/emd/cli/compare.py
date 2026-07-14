from __future__ import annotations

import warnings
from pathlib import Path
from typing import Annotated, Any

import typer

from emd.cli._app import app
from emd.cli._pipeline import ensure_file, load_step
from emd.cli._ui import Steps, console, header, output_panel


@app.command()
def compare(
    reference: Annotated[Path, typer.Argument(help="Reference dataset (e.g. train.csv)")],
    current: Annotated[Path, typer.Argument(help="Current dataset (e.g. test.csv)")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output directory")
    ] = Path("./reports"),
    threshold: Annotated[float, typer.Option("--threshold", help="PSI drift threshold")] = 0.2,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress progress output")] = False,
) -> None:
    """Compare two datasets for statistical drift. Exits 1 on a bad file.

    Example: emd compare train.csv test.csv
    """
    from emd.analysis import DriftAnalyzer
    from emd.charts import ChartRenderer
    from emd.report import MarkdownReportGenerator

    for p in (reference, current):
        ensure_file(p)

    if not quiet:
        header("compare", f"{reference.name} vs {current.name}")

    with Steps(quiet) as steps:
        df_ref = load_step(steps, reference, label="Load reference")
        df_cur = load_step(steps, current, label="Load current")

        def _analyze_drift() -> Any:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return DriftAnalyzer(psi_threshold=threshold).analyze(df_ref, df_cur)

        drift_result = steps.run("Analyze drift", _analyze_drift)

        out_dir = Path(output) / f"{reference.stem}_vs_{current.stem}"
        out_dir.mkdir(parents=True, exist_ok=True)

        renderer = ChartRenderer(out_dir)

        def _render_drift_charts() -> dict[str, Path]:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return renderer.drift_charts(df_ref, df_cur, drift_result)

        chart_paths = steps.run("Render drift charts", _render_drift_charts)

        report_path = steps.run(
            "Write drift report",
            lambda: MarkdownReportGenerator().generate_drift_report(
                result=drift_result,
                chart_paths=chart_paths,
                output_dir=out_dir,
                ref_name=reference.name,
                cur_name=current.name,
            ),
        )

    if not quiet:
        console.print()
        if drift_result.overall_drift:
            drifted = ", ".join(drift_result.drifted_columns)
            console.print(
                f"[bold red]Data drift detected[/bold red] — "
                f"{len(drift_result.drifted_columns)} columns: {drifted}"
            )
        else:
            console.print("[bold green]No significant drift detected.[/bold green]")
        console.print()
        output_panel({"Report": str(report_path)})
