from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from emd import __version__

app = typer.Typer(
    name="emd",
    help="Explain My Data — automated EDA reports from CSV/XLSX files.",
    add_completion=True,
    rich_markup_mode="rich",
)
schema_app = typer.Typer(name="schema", help="Schema contract generation and validation.")
app.add_typer(schema_app)
console = Console()
err_console = Console(stderr=True)


def _load(path: Path, sheet: str | None, parse_dates: list[str]) -> "pd.DataFrame":
    import pandas as pd
    from emd.loader import CSVLoader, XLSXLoader
    if path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        loader = XLSXLoader()
        return loader.load(path, sheet=sheet, parse_dates=parse_dates)
    loader = CSVLoader()
    return loader.load(path, parse_dates=parse_dates)


@app.command()
def analyze(
    file: Annotated[Path, typer.Argument(help="Path to CSV or XLSX file")],
    output: Annotated[str, typer.Option("--output", "-o", help="Output directory")] = "./reports",
    chart_format: Annotated[str, typer.Option("--chart-format", help="png or svg")] = "png",
    theme: Annotated[str, typer.Option("--theme", help="light or dark")] = "light",
    sheet: Annotated[Optional[str], typer.Option("--sheet", help="XLSX sheet name")] = None,
    parse_dates: Annotated[str, typer.Option("--parse-dates", help="Comma-separated date columns")] = "",
    drop_cols: Annotated[str, typer.Option("--drop-cols", help="Comma-separated columns to drop")] = "",
    sample: Annotated[Optional[int], typer.Option("--sample", help="Random sample size")] = None,
    skip_correlation: Annotated[bool, typer.Option("--skip-correlation")] = False,
    skip_outlier: Annotated[bool, typer.Option("--skip-outlier")] = False,
    use_iforest: Annotated[bool, typer.Option("--use-iforest")] = False,
    output_json: Annotated[bool, typer.Option("--output-json")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
    no_quality_gate: Annotated[bool, typer.Option("--no-quality-gate")] = False,
    target: Annotated[Optional[str], typer.Option("--target", help="Target column for Key Insights section")] = None,
) -> None:
    """Run full EDA analysis and generate a Markdown report."""
    from emd.analysis import (
        CorrelationAnalyzer,
        DistributionAnalyzer,
        MissingAnalyzer,
        OutlierAnalyzer,
        TargetAnalyzer,
    )
    from emd.charts import ChartRenderer
    from emd.config import ReportConfig
    from emd.quality import QualityChecker
    from emd.report import MarkdownReportGenerator

    if not file.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)

    cfg = ReportConfig(
        output_dir=output,
        chart_format=chart_format,
        theme=theme,
        skip_correlation=skip_correlation,
        skip_outlier=skip_outlier,
        use_iforest=use_iforest,
        sample_size=sample,
        parse_dates=[c.strip() for c in parse_dates.split(",") if c.strip()],
        drop_cols=[c.strip() for c in drop_cols.split(",") if c.strip()],
        sheet=sheet,
        output_json=output_json,
        quiet=quiet,
        no_quality_gate=no_quality_gate,
        target=target,
    )

    out_dir = Path(cfg.output_dir) / file.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    steps = [
        ("Loading data", lambda: _load(file, cfg.sheet, cfg.parse_dates)),
    ]

    def _run_step(label: str, fn):  # type: ignore[no-untyped-def]
        if not quiet:
            with Progress(SpinnerColumn(), TextColumn(f"[cyan]{label}..."), transient=True, console=console) as p:
                p.add_task("", total=None)
                return fn()
        return fn()

    df = _run_step("Loading data", lambda: _load(file, cfg.sheet, cfg.parse_dates))

    if cfg.drop_cols:
        df = df.drop(columns=[c for c in cfg.drop_cols if c in df.columns], errors="ignore")

    if cfg.sample_size and len(df) > cfg.sample_size:
        df = df.sample(n=cfg.sample_size, random_state=42)
        if not quiet:
            console.print(f"[yellow]Sampled {cfg.sample_size:,} rows from {len(df):,}[/yellow]")

    quality_report = _run_step(
        "Running quality checks",
        lambda: QualityChecker().check(df, no_quality_gate=cfg.no_quality_gate),
    )

    if not quiet:
        status_color = {"PASSED": "green", "PASSED WITH WARNINGS": "yellow", "FAILED": "red"}
        color = status_color.get(quality_report.status, "white")
        console.print(f"[{color}]Quality gate: {quality_report.status}[/{color}]")

    if cfg.target and cfg.target not in df.columns:
        err_console.print(f"[red]Target column '{cfg.target}' not found in dataset.[/red]")
        err_console.print(f"Available columns: {', '.join(df.columns.tolist())}")
        raise typer.Exit(1)

    _analysis_tasks: dict[str, Any] = {
        "dist": lambda: DistributionAnalyzer().analyze(df),
        "missing": lambda: MissingAnalyzer().analyze(df),
    }
    if not cfg.skip_correlation:
        _analysis_tasks["corr"] = lambda: CorrelationAnalyzer().analyze(df)
    if not cfg.skip_outlier:
        _analysis_tasks["outlier"] = lambda: OutlierAnalyzer(use_iforest=cfg.use_iforest).analyze(df)
    if cfg.target:
        _target = cfg.target
        _analysis_tasks["target"] = lambda: TargetAnalyzer().analyze(df, _target)  # type: ignore[arg-type]

    def _run_all_analyses() -> dict[str, Any]:
        _res: dict[str, Any] = {}
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(fn): key for key, fn in _analysis_tasks.items()}
            for future in as_completed(futures):
                _res[futures[future]] = future.result()
        return _res

    _results = _run_step("Analysing data", _run_all_analyses)
    dist_result = _results["dist"]
    missing_result = _results["missing"]
    corr_result = _results.get("corr")
    outlier_result = _results.get("outlier")
    target_result = _results.get("target")

    # Charts
    renderer = ChartRenderer(out_dir, fmt=cfg.chart_format, dpi=300, theme=cfg.theme)
    chart_paths: dict[str, Path] = {}
    chart_paths.update(_run_step("Rendering distribution charts",
                                  lambda: renderer.distribution_charts(df, dist_result)))
    if corr_result is not None:
        chart_paths.update(_run_step("Rendering correlation charts",
                                      lambda: renderer.correlation_charts(corr_result)))
    chart_paths.update(_run_step("Rendering missing value charts",
                                  lambda: renderer.missing_charts(missing_result)))
    if outlier_result is not None:
        chart_paths.update(_run_step("Rendering outlier charts",
                                      lambda: renderer.outlier_charts(df, outlier_result)))
    if target_result is not None:
        chart_paths.update(_run_step("Rendering target charts",
                                      lambda: renderer.target_charts(df, target_result)))

    # Report
    generator = MarkdownReportGenerator()
    report_path = _run_step(
        "Writing report",
        lambda: generator.generate(
            df=df,
            quality_report=quality_report,
            dist_result=dist_result,
            corr_result=corr_result,
            missing_result=missing_result,
            outlier_result=outlier_result,
            chart_paths=chart_paths,
            output_dir=out_dir,
            source_name=file.name,
            target_result=target_result,
        ),
    )

    if cfg.output_json:
        json_path = _run_step(
            "Writing JSON",
            lambda: generator.write_json(
                quality_report=quality_report,
                dist_result=dist_result,
                corr_result=corr_result,
                missing_result=missing_result,
                outlier_result=outlier_result,
                output_dir=out_dir,
            ),
        )
        if quiet:
            # Print JSON to stdout for subprocess consumers
            import json as _json
            print(_json.loads(json_path.read_text(encoding="utf-8")).__class__)
            sys.stdout.write(json_path.read_text(encoding="utf-8"))
            sys.stdout.flush()
            return

    if not quiet:
        console.print(f"\n[bold green]Report saved:[/bold green] {report_path}")
        console.print(f"[dim]Charts in:[/dim] {out_dir / 'charts'}")
        if cfg.output_json:
            console.print(f"[dim]JSON at:[/dim] {out_dir / 'analysis_results.json'}")


@app.command()
def compare(
    reference: Annotated[Path, typer.Argument(help="Reference dataset (e.g. train.csv)")],
    current: Annotated[Path, typer.Argument(help="Current dataset (e.g. test.csv)")],
    output: Annotated[str, typer.Option("--output", "-o")] = "./reports",
    threshold: Annotated[float, typer.Option("--threshold", help="PSI drift threshold")] = 0.2,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
) -> None:
    """Compare two datasets for statistical drift."""
    from emd.analysis import DriftAnalyzer
    from emd.charts import ChartRenderer
    from emd.report import MarkdownReportGenerator

    for p in (reference, current):
        if not p.exists():
            err_console.print(f"[red]File not found:[/red] {p}")
            raise typer.Exit(1)

    def _run_step(label: str, fn):  # type: ignore[no-untyped-def]
        if not quiet:
            with Progress(SpinnerColumn(), TextColumn(f"[cyan]{label}..."), transient=True, console=console) as p:
                p.add_task("", total=None)
                return fn()
        return fn()

    df_ref = _run_step("Loading reference", lambda: _load(reference, None, []))
    df_cur = _run_step("Loading current", lambda: _load(current, None, []))

    drift_result = _run_step(
        "Analysing drift",
        lambda: DriftAnalyzer(psi_threshold=threshold).analyze(df_ref, df_cur),
    )

    out_dir = Path(output) / f"{reference.stem}_vs_{current.stem}"
    out_dir.mkdir(parents=True, exist_ok=True)

    renderer = ChartRenderer(out_dir)
    chart_paths = _run_step(
        "Rendering drift charts",
        lambda: renderer.drift_charts(df_ref, df_cur, drift_result),
    )

    report_path = _run_step(
        "Writing drift report",
        lambda: MarkdownReportGenerator().generate_drift_report(
            result=drift_result,
            chart_paths=chart_paths,
            output_dir=out_dir,
            ref_name=reference.name,
            cur_name=current.name,
        ),
    )

    if not quiet:
        if drift_result.overall_drift:
            console.print(
                f"\n[bold red]DATA DRIFT DETECTED[/bold red] — "
                f"{len(drift_result.drifted_columns)} columns: {', '.join(drift_result.drifted_columns)}"
            )
        else:
            console.print("\n[bold green]No significant drift detected.[/bold green]")
        console.print(f"[bold green]Report saved:[/bold green] {report_path}")


@app.command()
def check(
    file: Annotated[Path, typer.Argument(help="CSV or XLSX file to quality-check")],
    sheet: Annotated[Optional[str], typer.Option("--sheet")] = None,
) -> None:
    """Run only the data quality gate and display results."""
    from emd.quality import QualityChecker

    if not file.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)

    df = _load(file, sheet, [])
    qr = QualityChecker().check(df, no_quality_gate=True)

    console.print(f"\n[bold]Quality Report — {file.name}[/bold]")
    console.print(f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Severity")
    table.add_column("Result")
    table.add_column("Recommendation")

    color_map = {"FATAL": "red", "WARNING": "yellow", "INFO": "blue"}
    for issue in qr.issues:
        color = color_map.get(issue.severity.value, "white")
        table.add_row(
            issue.check,
            f"[{color}]{issue.severity.value}[/{color}]",
            issue.result,
            issue.recommendation,
        )

    if qr.issues:
        console.print(table)
    else:
        console.print("[green]No issues detected — data looks clean.[/green]")

    status_color = {"PASSED": "green", "PASSED WITH WARNINGS": "yellow", "FAILED": "red"}
    color = status_color.get(qr.status, "white")
    console.print(f"\n[bold {color}]Overall: {qr.status}[/bold {color}]")


@app.command()
def sheets(
    file: Annotated[Path, typer.Argument(help="XLSX file to inspect")],
) -> None:
    """List sheets in an Excel file."""
    from emd.loader import XLSXLoader

    if not file.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)

    sheet_names = XLSXLoader().list_sheets(file)
    console.print(f"\n[bold]Sheets in {file.name}:[/bold]")
    for i, name in enumerate(sheet_names, 1):
        console.print(f"  {i}. {name}")


@app.command()
def batch(
    directory: Annotated[Path, typer.Argument(help="Directory containing CSV/XLSX files")],
    output: Annotated[str, typer.Option("--output", "-o")] = "./reports",
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
) -> None:
    """Run analyze on every CSV/XLSX file in a directory."""
    if not directory.is_dir():
        err_console.print(f"[red]Not a directory:[/red] {directory}")
        raise typer.Exit(1)

    files = list(directory.glob("*.csv")) + list(directory.glob("*.xlsx"))
    if not files:
        console.print("[yellow]No CSV/XLSX files found in directory.[/yellow]")
        return

    for f in sorted(files):
        console.print(f"\n[bold cyan]Processing:[/bold cyan] {f.name}")
        try:
            ctx = typer.Context(analyze)
            analyze.callback(  # type: ignore[attr-defined]
                file=f, output=output, chart_format="png", theme="light",
                sheet=None, parse_dates="", drop_cols="", sample=None,
                skip_correlation=False, skip_outlier=False, use_iforest=False,
                output_json=False, quiet=quiet, no_quality_gate=False,
            )
        except Exception as exc:
            err_console.print(f"[red]Failed:[/red] {f.name} — {exc}")


@app.command()
def info() -> None:
    """Show version and dependency status."""
    console.print(f"\n[bold]emd[/bold] version [cyan]{__version__}[/cyan]\n")

    deps = [
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("matplotlib", "matplotlib"),
        ("seaborn", "seaborn"),
        ("statsmodels", "statsmodels"),
        ("openpyxl", "openpyxl"),
        ("chardet", "chardet"),
        ("typer", "typer"),
        ("pyyaml", "yaml"),
    ]
    optional = [("scikit-learn (Isolation Forest)", "sklearn")]

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Package")
    table.add_column("Version")
    table.add_column("Status")

    for name, mod in deps + optional:
        try:
            import importlib
            m = importlib.import_module(mod)
            version = getattr(m, "__version__", "installed")
            status = "[green]OK[/green]"
        except ImportError:
            version = "—"
            status = "[yellow]optional — not installed[/yellow]" if (name, mod) in optional else "[red]MISSING[/red]"
        table.add_row(name, version, status)

    console.print(table)


@schema_app.command("init")
def schema_init(
    file: Annotated[Path, typer.Argument(help="CSV or XLSX file to generate schema from")],
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output path for schema YAML")] = None,
    name: Annotated[str, typer.Option("--name", help="Human-readable dataset name")] = "",
    sheet: Annotated[Optional[str], typer.Option("--sheet", help="XLSX sheet name")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output")] = False,
) -> None:
    """Generate a YAML schema contract from a data file."""
    if not file.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)

    import pandas as pd
    from emd.schema.contract import save_contract
    from emd.schema.generator import ContractGenerator

    df = _load(file, sheet, [])
    contract_name = name or file.stem
    contract = ContractGenerator.from_dataframe(df, name=contract_name)

    out_path = output or (file.parent / "schemas" / f"{file.stem}_schema.yaml")
    save_contract(contract, out_path)

    if not quiet:
        console.print(f"\n[bold green]Schema contract generated:[/bold green] {out_path}\n")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Column")
        table.add_column("Dtype")
        table.add_column("Required")
        table.add_column("Missing ≤")
        table.add_column("Range / Values")
        for col, rule in contract.columns.items():
            missing_str = f"{rule.max_missing_pct}%" if rule.max_missing_pct is not None else "—"
            if rule.dtype == "numeric":
                range_str = f"[{rule.min}, {rule.max}]" if rule.min is not None else "—"
            elif rule.allowed_values is not None:
                vals = rule.allowed_values[:5]
                range_str = str(vals) + ("…" if len(rule.allowed_values) > 5 else "")
            else:
                range_str = "—"
            table.add_row(col, rule.dtype, str(rule.required), missing_str, range_str)
        console.print(table)
        console.print(f"\n[dim]{len(contract.columns)} columns | min_rows={contract.global_rules.min_rows}[/dim]\n")


@schema_app.command("validate")
def schema_validate(
    file: Annotated[Path, typer.Argument(help="CSV or XLSX file to validate")],
    schema: Annotated[Path, typer.Option("--schema", "-s", help="Path to schema YAML contract")],
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output")] = False,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
    sheet: Annotated[Optional[str], typer.Option("--sheet", help="XLSX sheet name")] = None,
) -> None:
    """Validate a data file against a YAML schema contract. Exits 0 on pass, 1 on fail."""
    if not file.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)
    if not schema.exists():
        err_console.print(f"[red]Schema not found:[/red] {schema}")
        raise typer.Exit(1)

    from emd.schema.contract import load_contract
    from emd.schema.validator import SchemaValidator

    df = _load(file, sheet, [])
    contract = load_contract(schema)
    result = SchemaValidator.validate(df, contract, strict=strict)

    if not quiet:
        if result.violations:
            table = Table(show_header=True, header_style="bold")
            table.add_column("Column")
            table.add_column("Check")
            table.add_column("Expected")
            table.add_column("Actual")
            table.add_column("Severity")
            for v in result.violations:
                sev_style = "[red]error[/red]" if v.severity == "error" else "[yellow]warning[/yellow]"
                table.add_row(v.column, v.check, v.expected, v.actual, sev_style)
            console.print(f"\n[bold]Validation:[/bold] {file.name}  →  schema: {schema.name}\n")
            console.print(table)
        if result.passed:
            console.print(f"\n[bold green]PASSED[/bold green] — {len(result.violations)} warning(s)\n")
        else:
            errors = sum(1 for v in result.violations if v.severity == "error")
            warnings = sum(1 for v in result.violations if v.severity == "warning")
            console.print(f"\n[bold red]FAILED[/bold red] — {errors} error(s), {warnings} warning(s)\n")
    elif not result.passed:
        errors = sum(1 for v in result.violations if v.severity == "error")
        warnings = sum(1 for v in result.violations if v.severity == "warning")
        err_console.print(f"Validation failed: {errors} error(s), {warnings} warning(s)")

    raise typer.Exit(0 if result.passed else 1)


if __name__ == "__main__":
    app()
