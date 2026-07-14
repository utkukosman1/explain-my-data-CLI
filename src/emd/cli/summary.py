from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer
from rich.table import Table

from emd.cli._app import app
from emd.cli._pipeline import (
    ensure_file,
    ensure_target,
    load_step,
    prepare_df,
    quality_gate_step,
    run_analyzers,
    split_csv_option,
)
from emd.cli._ui import Steps, console, header

if TYPE_CHECKING:
    import pandas as pd

# Thresholds for surfacing a Key Issue in the terminal Summary. These only decide what
# gets printed to the terminal — they never affect analyzer output or report.md.
_SUMMARY_MISSING_COL_THRESHOLD = 0.10
_SUMMARY_OUTLIER_COL_THRESHOLD = 0.10
_SUMMARY_IDENTIFIER_UNIQUE_PCT = 0.98
_SUMMARY_VIF_SEVERE = 10
_SUMMARY_SKEW_THRESHOLD = 2.0
_SUMMARY_MAX_ISSUES = 5


def _summary_key_issues(
    df: pd.DataFrame,
    dist_result: Any,
    missing_result: Any,
    corr_result: Any,
    outlier_result: Any,
    dup_count: int,
) -> list[str]:
    """Rank findings already computed by the analyzers into at most 5 terminal bullets.

    Each candidate is (tier, magnitude, message); lower tier = more important. Sorting by
    (tier, -magnitude) means "how bad" only breaks ties within the same kind of issue —
    it never lets a mild instance of one tier outrank a real instance of a higher tier.
    """
    candidates: list[tuple[int, float, str]] = []

    for col in dist_result.numeric:
        if col.count > 0 and col.unique_count == 1:
            candidates.append(
                (1, 1.0, f"{col.name} has only one unique value — carries no information.")
            )

    if dup_count > 0:
        plural = "s" if dup_count != 1 else ""
        candidates.append((2, float(dup_count), f"{dup_count:,} duplicate row{plural} detected."))

    for col in missing_result.columns:
        if col.missing_pct >= _SUMMARY_MISSING_COL_THRESHOLD:
            candidates.append((
                3, col.missing_pct,
                f"{col.missing_pct:.1%} missing values detected in {col.name}.",
            ))

    vif_flagged_cols: set[str] = set()
    if corr_result is not None and corr_result.vif:
        for name, v in corr_result.vif.items():
            if v > _SUMMARY_VIF_SEVERE:
                vif_flagged_cols.add(name)
                candidates.append(
                    (4, v, f"Severe multicollinearity detected for {name} (VIF = {v:.1f}).")
                )

    if corr_result is not None:
        for col_a, col_b, r, _label in corr_result.strong_pairs:
            # Skip pairs already covered by a VIF finding above — same underlying
            # relationship, and repeating it wastes a Key Issues slot.
            if col_a in vif_flagged_cols or col_b in vif_flagged_cols:
                continue
            candidates.append(
                (5, abs(r), f"Strong multicollinearity detected between {col_a} and {col_b}.")
            )

    for col in dist_result.numeric:
        if col.count == 0 or not any("may be an ID" in a for a in col.assumptions):
            continue
        # High cardinality alone also fires for continuous float measurements — only
        # trust it as an identifier when every value is whole-numbered (true IDs are).
        values = df[col.name].dropna()
        if not values.empty and (values % 1 == 0).all():
            candidates.append((6, col.unique_pct, f"{col.name} appears to be an identifier."))
    for col in dist_result.categorical:
        if col.count >= 20 and col.unique_pct >= _SUMMARY_IDENTIFIER_UNIQUE_PCT:
            candidates.append((6, col.unique_pct, f"{col.name} appears to be an identifier."))

    for col in dist_result.numeric:
        is_nan = col.skewness != col.skewness
        if not is_nan and abs(col.skewness) > _SUMMARY_SKEW_THRESHOLD:
            candidates.append((7, abs(col.skewness), f"High skew detected in {col.name}."))

    if outlier_result is not None:
        for col in outlier_result.columns:
            if col.iqr_pct >= _SUMMARY_OUTLIER_COL_THRESHOLD:
                candidates.append((
                    8, col.iqr_pct,
                    f"{col.iqr_pct:.1%} of values in {col.name} are outliers (IQR method).",
                ))

    candidates.sort(key=lambda c: (c[0], -c[1]))
    return [message for _tier, _magnitude, message in candidates[:_SUMMARY_MAX_ISSUES]]


def _summary_at_a_glance(
    df: pd.DataFrame,
    dist_result: Any,
    missing_result: Any,
    target: str | None,
    dup_count: int,
) -> dict[str, str]:
    items = {
        "Rows": f"{len(df):,}",
        "Columns": f"{df.shape[1]:,}",
        "Missing Values": f"{missing_result.global_missing_pct:.1%}",
        "Duplicate Rows": f"{dup_count:,}",
        "Numeric Features": f"{len(dist_result.numeric):,}",
        "Categorical Features": f"{len(dist_result.categorical):,}",
    }
    if target:
        items["Target Column"] = target
    return items


def _render_summary(
    df: pd.DataFrame,
    dist_result: Any,
    missing_result: Any,
    corr_result: Any,
    outlier_result: Any,
    target: str | None,
) -> None:
    """Prints the Key Issues + At a Glance recap, built entirely from analyzer
    results already computed by the caller — no new statistics are run here."""
    dup_count = int(df.duplicated().sum())
    issues = _summary_key_issues(
        df, dist_result, missing_result, corr_result, outlier_result, dup_count
    )
    glance = _summary_at_a_glance(df, dist_result, missing_result, target, dup_count)

    console.print()
    console.rule("[bold]Summary[/bold]", style="dim", align="left")
    console.print("[bold]Key Issues[/bold]")
    if issues:
        for issue in issues:
            console.print(f"  • {issue}")
    else:
        console.print("  No significant issues detected.")
    console.print()
    console.print("[bold]At a Glance[/bold]")
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    for label, value in glance.items():
        grid.add_row(label, value)
    console.print(grid)


@app.command()
def summary(
    file: Annotated[Path, typer.Argument(help="Path to CSV or XLSX file")],
    sheet: Annotated[str | None, typer.Option("--sheet", help="XLSX sheet name")] = None,
    parse_dates: Annotated[
        str, typer.Option("--parse-dates", help="Comma-separated date columns")
    ] = "",
    drop_cols: Annotated[
        str, typer.Option("--drop-cols", help="Comma-separated columns to drop")
    ] = "",
    sample: Annotated[int | None, typer.Option("--sample", help="Random sample size")] = None,
    skip_correlation: Annotated[
        bool, typer.Option("--skip-correlation", help="Skip correlation analysis")
    ] = False,
    skip_outlier: Annotated[
        bool, typer.Option("--skip-outlier", help="Skip outlier detection")
    ] = False,
    no_quality_gate: Annotated[
        bool, typer.Option("--no-quality-gate", help="Continue even if the quality gate fails")
    ] = False,
    target: Annotated[
        str | None, typer.Option("--target", help="Target column to show in At a Glance")
    ] = None,
) -> None:
    """Print a fast terminal recap of a dataset — Key Issues + At a Glance.

    Nothing is written to disk: no charts, no report.md, no JSON. Runs the same
    analyzers as `analyze` but skips chart rendering and report generation, so it's
    the quickest way to get oriented on a new dataset. Exits 1 on a bad file or
    failed quality gate.
    Example: emd summary data.csv
    """
    ensure_file(file)

    header("summary", file.name)

    with Steps(False) as steps:
        df = load_step(steps, file, sheet, split_csv_option(parse_dates))
        df = prepare_df(df, split_csv_option(drop_cols), sample)
        quality_gate_step(steps, df, no_quality_gate, show_status=False)
        ensure_target(steps, df, target)
        results = steps.run(
            "Analyze data",
            lambda: run_analyzers(
                df,
                skip_correlation=skip_correlation,
                skip_outlier=skip_outlier,
            ),
        )

    _render_summary(
        df, results["dist"], results["missing"],
        results.get("corr"), results.get("outlier"), target,
    )
