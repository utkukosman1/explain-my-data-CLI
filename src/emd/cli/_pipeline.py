"""Shared command pipeline: load → prepare → quality gate → run analyzers.

Every dataset-consuming command (analyze, summary, doctor) runs the same opening
sequence; these helpers keep that sequence in one place. Heavy imports (pandas,
analyzers) stay inside functions so `emd --help` startup remains fast.
"""
from __future__ import annotations

import warnings
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from emd.cli._ui import STATUS_COLORS, Steps, console, err_console

if TYPE_CHECKING:
    import pandas as pd


def ensure_file(path: Path) -> None:
    """Exit 1 with a consistent message if the input file does not exist."""
    if not path.exists():
        err_console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(1)


def load_df(path: Path, sheet: str | None, parse_dates: list[str]) -> pd.DataFrame:
    from emd.loader import CSVLoader, XLSXLoader

    if path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        return XLSXLoader().load(path, sheet=sheet, parse_dates=parse_dates)
    return CSVLoader().load(path, parse_dates=parse_dates)


def load_or_exit(path: Path, sheet: str | None = None) -> pd.DataFrame:
    try:
        return load_df(path, sheet, [])
    except Exception as exc:
        err_console.print(f"[red]Could not read {path.name}:[/red] {exc}")
        raise typer.Exit(1) from exc


def load_step(
    steps: Steps,
    file: Path,
    sheet: str | None = None,
    parse_dates: list[str] | None = None,
    label: str = "Load data",
) -> pd.DataFrame:
    """Load the file as one checklist step; exits 1 with the read error on failure."""
    try:
        return steps.run(
            label, lambda: load_df(file, sheet, parse_dates or []),
            detail=lambda d: f"[dim]{d.shape[0]:,} rows x {d.shape[1]} columns[/dim]",
        )
    except Exception as exc:
        steps.stop()
        err_console.print(f"[red]Could not read {file.name}:[/red] {exc}")
        raise typer.Exit(1) from exc


def prepare_df(
    df: pd.DataFrame,
    drop_cols: list[str] | None = None,
    sample: int | None = None,
    quiet: bool = False,
) -> pd.DataFrame:
    """Apply --drop-cols and --sample the same way for every command."""
    if drop_cols:
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
    if sample and len(df) > sample:
        original_rows = len(df)
        df = df.sample(n=sample, random_state=42)
        if not quiet:
            console.print(f"[yellow]Sampled {sample:,} rows from {original_rows:,}[/yellow]")
    return df


def quality_gate_step(
    steps: Steps, df: pd.DataFrame, no_quality_gate: bool, show_status: bool = True
) -> Any:
    """Run the quality gate as one checklist step; exits 1 on a FATAL result unless
    --no-quality-gate was passed. Returns the QualityReport."""
    from emd.quality import DataQualityError, QualityChecker

    def _status_detail(qr: Any) -> str:
        color = STATUS_COLORS.get(qr.status, "white")
        return f"[{color}]{qr.status}[/{color}]"

    detail = _status_detail if show_status else None

    try:
        return steps.run(
            "Run quality checks",
            lambda: QualityChecker().check(df, no_quality_gate=no_quality_gate),
            detail=detail,
        )
    except DataQualityError as exc:
        steps.stop()
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


def ensure_target(steps: Steps, df: pd.DataFrame, target: str | None) -> None:
    """Exit 1 if a requested --target column is not in the dataset."""
    if target and target not in df.columns:
        steps.stop()
        err_console.print(f"[red]Target column '{target}' not found in dataset.[/red]")
        err_console.print(f"Available columns: {', '.join(df.columns.tolist())}")
        raise typer.Exit(1)


def run_analyzers(
    df: pd.DataFrame,
    *,
    skip_correlation: bool = False,
    skip_outlier: bool = False,
    target: str | None = None,
    outlier_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the shared analyzers concurrently. Returns a dict with keys
    "dist", "missing", and (when not skipped) "corr", "outlier", "target"."""
    from emd.analysis import (
        CorrelationAnalyzer,
        DistributionAnalyzer,
        MissingAnalyzer,
        OutlierAnalyzer,
        TargetAnalyzer,
    )

    tasks: dict[str, Callable[[], Any]] = {
        "dist": lambda: DistributionAnalyzer().analyze(df),
        "missing": lambda: MissingAnalyzer().analyze(df),
    }
    if not skip_correlation:
        tasks["corr"] = lambda: CorrelationAnalyzer().analyze(df)
    if not skip_outlier:
        kwargs = outlier_kwargs or {}
        tasks["outlier"] = lambda: OutlierAnalyzer(**kwargs).analyze(df)
    if target:
        target_col = target
        tasks["target"] = lambda: TargetAnalyzer().analyze(df, target_col)

    results: dict[str, Any] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(fn): key for key, fn in tasks.items()}
            for future in as_completed(futures):
                results[futures[future]] = future.result()
    return results


def split_csv_option(raw: str) -> list[str]:
    """Parse a comma-separated CLI option into a clean list."""
    return [c.strip() for c in raw.split(",") if c.strip()]
