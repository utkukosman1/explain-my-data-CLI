from __future__ import annotations

import contextlib
import sys
import warnings
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Annotated, Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from emd import __version__


class Theme(StrEnum):
    light = "light"
    dark = "dark"


class ChartFormat(StrEnum):
    png = "png"
    svg = "svg"


STATUS_COLORS = {"PASSED": "green", "PASSED WITH WARNINGS": "yellow", "FAILED": "red"}
SEVERITY_COLORS = {
    "FATAL": "red", "WARNING": "yellow", "INFO": "blue", "error": "red", "warning": "yellow",
}

# Force UTF-8 on stdout/stderr: on Windows, redirected/piped output falls back to the
# system codepage (e.g. cp1252), which can't encode the spinner/box-drawing characters
# rich uses — this crashes analyze/compare with UnicodeEncodeError whenever output isn't
# a live terminal (piping to a file, CI logs, etc).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

app = typer.Typer(
    name="emd",
    help="Explain My Data — automated EDA reports from CSV/XLSX files.",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)
schema_app = typer.Typer(name="schema", help="Schema contract generation and validation.")
app.add_typer(schema_app)
console = Console()
err_console = Console(stderr=True)


def _header(title: str, subtitle: str = "") -> None:
    """Rule-style section header shown at the start of a command run."""
    text = f"[bold]{title}[/bold]"
    if subtitle:
        text += f" [dim]· {subtitle}[/dim]"
    console.rule(text, style="dim", align="left")


def _output_panel(items: dict[str, str]) -> None:
    """Boxed summary of generated artifacts, shown at the end of a command run."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    for label, value in items.items():
        grid.add_row(label, value)
    console.print(Panel(grid, title="Output", title_align="left", border_style="dim", expand=False))


def _make_table(*columns: str) -> Table:
    """Table with the house style shared by check/info/schema output."""
    table = Table(show_header=True, header_style="bold cyan")
    for col in columns:
        table.add_column(col)
    return table


def _status(label: str, quiet: bool = False):  # type: ignore[no-untyped-def]
    """Spinner for a single-shot operation; a no-op under --quiet."""
    if quiet:
        return contextlib.nullcontext()
    return console.status(label)


class _Steps:
    """Persistent step checklist: spinner while a step runs, checkmark once it's done.

    Unlike a fresh transient Progress per step, this keeps every completed step visible
    for the whole command run, so the terminal reads as a history of what happened
    rather than a sequence of messages that vanish as soon as the next one starts.
    A no-op under --quiet.
    """

    def __init__(self, quiet: bool) -> None:
        self._progress: Progress | None = None
        if not quiet:
            self._progress = Progress(
                SpinnerColumn(finished_text="[green]✓[/green]"),
                TextColumn("{task.description}"),
                console=console,
                transient=False,
            )

    def __enter__(self) -> "_Steps":
        if self._progress is not None:
            self._progress.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._progress is not None:
            self._progress.__exit__(exc_type, exc_val, exc_tb)

    def stop(self) -> None:
        """Close the checklist early — call before printing an error to a different
        console, so a failed step doesn't leave a frozen spinner glyph behind it."""
        if self._progress is not None:
            self._progress.stop()

    def run(
        self, label: str, fn: Callable[[], Any], detail: Callable[[Any], str] | None = None
    ) -> Any:
        """Run fn() as one checklist step. `detail`, if given, formats a status suffix
        from the result — pass its own rich markup (e.g. "[dim]...[/dim]" or a color).
        If fn() raises, the spinner row is replaced with a plain "✗ label" line (rather
        than left as a frozen spinner glyph) and the exception is re-raised unchanged."""
        if self._progress is None:
            return fn()
        task_id = self._progress.add_task(f"[cyan]{label}[/cyan]", total=1)
        try:
            result = fn()
        except Exception:
            # Remove the failed row, then fully stop (not just pause) the live display —
            # this flushes already-completed steps to real scrollback in the right order
            # before printing the failure line as a plain, static line below them.
            self._progress.remove_task(task_id)
            self._progress.stop()
            console.print(f"[red]✗[/red] {label}")
            raise
        description = label
        if detail is not None:
            try:
                description = f"{label}  {detail(result)}"
            except Exception:
                pass
        self._progress.update(task_id, completed=1, description=description)
        return result


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"emd version [cyan]{__version__}[/cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Show the version and exit"
        ),
    ] = None,
) -> None:
    """Explain My Data — automated EDA reports from CSV/XLSX files."""


def _load(path: Path, sheet: str | None, parse_dates: list[str]) -> "pd.DataFrame":
    import pandas as pd
    from emd.loader import CSVLoader, XLSXLoader
    if path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        loader = XLSXLoader()
        return loader.load(path, sheet=sheet, parse_dates=parse_dates)
    loader = CSVLoader()
    return loader.load(path, parse_dates=parse_dates)


def _load_or_exit(path: Path, sheet: str | None = None) -> "pd.DataFrame":
    try:
        return _load(path, sheet, [])
    except Exception as exc:
        err_console.print(f"[red]Could not read {path.name}:[/red] {exc}")
        raise typer.Exit(1) from exc


def _analyze_impl(
    file: Path,
    output: str = "./reports",
    chart_format: str = "png",
    theme: str = "light",
    sheet: str | None = None,
    parse_dates: str = "",
    drop_cols: str = "",
    sample: int | None = None,
    skip_correlation: bool = False,
    skip_outlier: bool = False,
    use_iforest: bool = False,
    output_json: bool = False,
    quiet: bool = False,
    no_quality_gate: bool = False,
    target: str | None = None,
) -> None:
    from emd.analysis import (
        CorrelationAnalyzer,
        DistributionAnalyzer,
        MissingAnalyzer,
        OutlierAnalyzer,
        TargetAnalyzer,
    )
    from emd.charts import ChartRenderer
    from emd.config import ReportConfig
    from emd.quality import DataQualityError, QualityChecker
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

    if not quiet:
        _header("analyze", file.name)

    with _Steps(quiet) as steps:
        try:
            df = steps.run(
                "Load data", lambda: _load(file, cfg.sheet, cfg.parse_dates),
                detail=lambda d: f"[dim]{d.shape[0]:,} rows x {d.shape[1]} columns[/dim]",
            )
        except Exception as exc:
            steps.stop()
            err_console.print(f"[red]Could not read {file.name}:[/red] {exc}")
            raise typer.Exit(1) from exc

        if cfg.drop_cols:
            df = df.drop(columns=[c for c in cfg.drop_cols if c in df.columns], errors="ignore")

        if cfg.sample_size and len(df) > cfg.sample_size:
            df = df.sample(n=cfg.sample_size, random_state=42)
            if not quiet:
                console.print(f"[yellow]Sampled {cfg.sample_size:,} rows from {len(df):,}[/yellow]")

        try:
            quality_report = steps.run(
                "Run quality checks",
                lambda: QualityChecker().check(df, no_quality_gate=cfg.no_quality_gate),
                detail=lambda qr: (
                    f"[{STATUS_COLORS.get(qr.status, 'white')}]{qr.status}"
                    f"[/{STATUS_COLORS.get(qr.status, 'white')}]"
                ),
            )
        except DataQualityError as exc:
            steps.stop()
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        if cfg.target and cfg.target not in df.columns:
            steps.stop()
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
            _analysis_tasks["outlier"] = (
                lambda: OutlierAnalyzer(use_iforest=cfg.use_iforest).analyze(df)
            )
        if cfg.target:
            _target = cfg.target
            _analysis_tasks["target"] = (
                lambda: TargetAnalyzer().analyze(df, _target)  # type: ignore[arg-type]
            )

        def _run_all_analyses() -> dict[str, Any]:
            _res: dict[str, Any] = {}
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with ThreadPoolExecutor() as executor:
                    futures = {executor.submit(fn): key for key, fn in _analysis_tasks.items()}
                    for future in as_completed(futures):
                        _res[futures[future]] = future.result()
            return _res

        _results = steps.run("Analyze data", _run_all_analyses)
        dist_result = _results["dist"]
        missing_result = _results["missing"]
        corr_result = _results.get("corr")
        outlier_result = _results.get("outlier")
        target_result = _results.get("target")

        # Charts
        renderer = ChartRenderer(out_dir, fmt=cfg.chart_format, dpi=300, theme=cfg.theme)
        chart_paths: dict[str, Path] = {}

        def _render(fn: Callable[..., dict[str, Path]], *args: Any) -> dict[str, Path]:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return fn(*args)

        dist_fn = renderer.distribution_charts
        chart_paths.update(steps.run(
            "Render distribution charts", lambda: _render(dist_fn, df, dist_result),
        ))
        if corr_result is not None:
            corr_fn = renderer.correlation_charts
            chart_paths.update(steps.run(
                "Render correlation charts", lambda: _render(corr_fn, corr_result),
            ))
        missing_fn = renderer.missing_charts
        chart_paths.update(steps.run(
            "Render missing value charts", lambda: _render(missing_fn, missing_result),
        ))
        if outlier_result is not None:
            outlier_fn = renderer.outlier_charts
            chart_paths.update(steps.run(
                "Render outlier charts", lambda: _render(outlier_fn, df, outlier_result),
            ))
        if target_result is not None:
            target_fn = renderer.target_charts
            chart_paths.update(steps.run(
                "Render target charts", lambda: _render(target_fn, df, target_result),
            ))

        if not quiet:
            for failure in renderer.failures:
                console.print(f"[yellow]Skipped chart —[/yellow] {failure}")

        # Report
        generator = MarkdownReportGenerator()
        report_path = steps.run(
            "Write report",
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

        json_path: Path | None = None
        if cfg.output_json:
            json_path = steps.run(
                "Write JSON",
                lambda: generator.write_json(
                    quality_report=quality_report,
                    dist_result=dist_result,
                    corr_result=corr_result,
                    missing_result=missing_result,
                    outlier_result=outlier_result,
                    output_dir=out_dir,
                    target_result=target_result,
                ),
            )

    if quiet:
        if json_path is not None:
            # Print JSON to stdout for subprocess consumers
            sys.stdout.write(json_path.read_text(encoding="utf-8"))
            sys.stdout.flush()
        return

    chart_count = len(set(chart_paths.values()))
    output_items = {
        "Report": str(report_path),
        "Charts": f"{out_dir / 'charts'}  [dim]({chart_count} files)[/dim]",
    }
    if json_path is not None:
        output_items["JSON"] = str(json_path)
    console.print()
    _output_panel(output_items)


@app.command()
def analyze(
    file: Annotated[Path, typer.Argument(help="Path to CSV or XLSX file")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output directory")
    ] = Path("./reports"),
    chart_format: Annotated[
        ChartFormat, typer.Option("--chart-format", help="Chart output format")
    ] = ChartFormat.png,
    theme: Annotated[Theme, typer.Option("--theme", help="Chart color theme")] = Theme.light,
    sheet: Annotated[Optional[str], typer.Option("--sheet", help="XLSX sheet name")] = None,
    parse_dates: Annotated[
        str, typer.Option("--parse-dates", help="Comma-separated date columns")
    ] = "",
    drop_cols: Annotated[
        str, typer.Option("--drop-cols", help="Comma-separated columns to drop")
    ] = "",
    sample: Annotated[Optional[int], typer.Option("--sample", help="Random sample size")] = None,
    skip_correlation: Annotated[
        bool, typer.Option("--skip-correlation", help="Skip correlation analysis")
    ] = False,
    skip_outlier: Annotated[
        bool, typer.Option("--skip-outlier", help="Skip outlier detection")
    ] = False,
    use_iforest: Annotated[
        bool, typer.Option("--use-iforest", help="Add Isolation Forest to outlier methods")
    ] = False,
    output_json: Annotated[
        bool, typer.Option("--output-json", help="Also write analysis_results.json")
    ] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress progress output")] = False,
    no_quality_gate: Annotated[
        bool, typer.Option("--no-quality-gate", help="Continue even if the quality gate fails")
    ] = False,
    target: Annotated[
        Optional[str], typer.Option("--target", help="Target column for Key Insights section")
    ] = None,
) -> None:
    """Run full EDA analysis and generate a Markdown report.

    Exits 1 on a bad file or failed quality gate.
    Example: emd analyze data.csv --target SalePrice
    """
    _analyze_impl(
        file=file, output=str(output), chart_format=chart_format.value, theme=theme.value,
        sheet=sheet, parse_dates=parse_dates, drop_cols=drop_cols, sample=sample,
        skip_correlation=skip_correlation, skip_outlier=skip_outlier, use_iforest=use_iforest,
        output_json=output_json, quiet=quiet, no_quality_gate=no_quality_gate, target=target,
    )


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
        if not p.exists():
            err_console.print(f"[red]File not found:[/red] {p}")
            raise typer.Exit(1)

    if not quiet:
        _header("compare", f"{reference.name} vs {current.name}")

    with _Steps(quiet) as steps:

        def _safe_load(label: str, path: Path):  # type: ignore[no-untyped-def]
            try:
                return steps.run(
                    label, lambda: _load(path, None, []),
                    detail=lambda d: f"[dim]{d.shape[0]:,} rows x {d.shape[1]} columns[/dim]",
                )
            except Exception as exc:
                steps.stop()
                err_console.print(f"[red]Could not read {path.name}:[/red] {exc}")
                raise typer.Exit(1) from exc

        df_ref = _safe_load("Load reference", reference)
        df_cur = _safe_load("Load current", current)

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
            console.print(
                f"[bold red]Data drift detected[/bold red] — "
                f"{len(drift_result.drifted_columns)} columns: {', '.join(drift_result.drifted_columns)}"
            )
        else:
            console.print("[bold green]No significant drift detected.[/bold green]")
        console.print()
        _output_panel({"Report": str(report_path)})


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

    _header("check", file.name)

    with console.status("Loading data..."):
        df = _load_or_exit(file, sheet)
        qr = QualityChecker().check(df, no_quality_gate=True)

    console.print(
        f"Shape: [bold]{df.shape[0]:,}[/bold] rows x [bold]{df.shape[1]}[/bold] columns\n"
    )

    if qr.issues:
        table = _make_table("Check", "Severity", "Result", "Recommendation")
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


@app.command()
def sheets(
    file: Annotated[Path, typer.Argument(help="XLSX file to inspect")],
) -> None:
    """List sheets in an Excel file."""
    from emd.loader import XLSXLoader

    if not file.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)

    _header("sheets", file.name)

    try:
        with console.status("Reading workbook..."):
            sheet_names = XLSXLoader().list_sheets(file)
    except Exception as exc:
        err_console.print(f"[red]Could not read {file.name}:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print()
    for i, name in enumerate(sheet_names, 1):
        console.print(f"  [cyan]{i}.[/cyan] {name}")


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
        _header("batch", f"{directory}  ·  {len(files)} files")

    succeeded = 0
    failed_files: list[str] = []
    for i, f in enumerate(files):
        if not quiet and i > 0:
            console.print()
        try:
            _analyze_impl(
                file=f, output=str(output), chart_format="png", theme="light",
                sheet=None, parse_dates="", drop_cols="", sample=None,
                skip_correlation=False, skip_outlier=False, use_iforest=False,
                output_json=False, quiet=quiet, no_quality_gate=False,
            )
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


@app.command()
def info() -> None:
    """Show version and dependency status."""
    _header("info", f"v{__version__}")

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

    table = _make_table("Package", "Version", "Status")

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

    console.print()
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

    if not quiet:
        _header("schema init", file.name)

    with _status("Loading data...", quiet):
        df = _load_or_exit(file, sheet)
        contract_name = name or file.stem
        contract = ContractGenerator.from_dataframe(df, name=contract_name)
        out_path = output or (file.parent / "schemas" / f"{file.stem}_schema.yaml")
        save_contract(contract, out_path)

    if not quiet:
        console.print()
        table = _make_table("Column", "Dtype", "Required", "Missing <=", "Range / Values")
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
        console.print()
        min_rows = contract.global_rules.min_rows
        col_detail = f"{len(contract.columns)}  [dim](min_rows={min_rows})[/dim]"
        _output_panel({"Schema": str(out_path), "Columns": col_detail})


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

    if not quiet:
        _header("schema validate", f"{file.name} -> {schema.name}")

    with _status("Loading data...", quiet):
        df = _load_or_exit(file, sheet)
        contract = load_contract(schema)
        result = SchemaValidator.validate(df, contract, strict=strict)

    if not quiet:
        console.print()
        if result.violations:
            table = _make_table("Column", "Check", "Expected", "Actual", "Severity")
            for v in result.violations:
                color = SEVERITY_COLORS.get(v.severity, "white")
                sev_cell = f"[{color}]{v.severity}[/{color}]"
                table.add_row(v.column, v.check, v.expected, v.actual, sev_cell)
            console.print(table)
            console.print()
        if result.passed:
            console.print(
                f"[bold green]PASSED[/bold green] — {len(result.violations)} warning(s)\n"
            )
        else:
            error_count = sum(1 for v in result.violations if v.severity == "error")
            warning_count = sum(1 for v in result.violations if v.severity == "warning")
            console.print(
                f"[bold red]FAILED[/bold red] — {error_count} error(s), "
                f"{warning_count} warning(s)\n"
            )
    elif not result.passed:
        error_count = sum(1 for v in result.violations if v.severity == "error")
        warning_count = sum(1 for v in result.violations if v.severity == "warning")
        err_console.print(f"Validation failed: {error_count} error(s), {warning_count} warning(s)")

    raise typer.Exit(0 if result.passed else 1)


if __name__ == "__main__":
    app()
