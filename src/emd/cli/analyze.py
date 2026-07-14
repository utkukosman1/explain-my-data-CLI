from __future__ import annotations

import sys
import warnings
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

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
from emd.cli._ui import Steps, console, header, output_panel


class Theme(StrEnum):
    light = "light"
    dark = "dark"


class ChartFormat(StrEnum):
    png = "png"
    svg = "svg"


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
    from emd.charts import ChartRenderer
    from emd.config import ReportConfig
    from emd.report import MarkdownReportGenerator

    ensure_file(file)

    cfg = ReportConfig(
        output_dir=output,
        chart_format=chart_format,
        theme=theme,
        skip_correlation=skip_correlation,
        skip_outlier=skip_outlier,
        use_iforest=use_iforest,
        sample_size=sample,
        parse_dates=split_csv_option(parse_dates),
        drop_cols=split_csv_option(drop_cols),
        sheet=sheet,
        output_json=output_json,
        quiet=quiet,
        no_quality_gate=no_quality_gate,
        target=target,
    )

    out_dir = Path(cfg.output_dir) / file.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    if not quiet:
        header("analyze", file.name)

    with Steps(quiet) as steps:
        df = load_step(steps, file, cfg.sheet, cfg.parse_dates)
        df = prepare_df(df, cfg.drop_cols, cfg.sample_size, quiet)
        quality_report = quality_gate_step(steps, df, cfg.no_quality_gate)
        ensure_target(steps, df, cfg.target)

        results = steps.run(
            "Analyze data",
            lambda: run_analyzers(
                df,
                skip_correlation=cfg.skip_correlation,
                skip_outlier=cfg.skip_outlier,
                target=cfg.target,
                outlier_kwargs={
                    "iqr_multiplier": cfg.iqr_multiplier,
                    "iqr_extreme_multiplier": cfg.iqr_extreme_multiplier,
                    "zscore_threshold": cfg.zscore_threshold,
                    "mzscore_threshold": cfg.mzscore_threshold,
                    "use_iforest": cfg.use_iforest,
                    "contamination": cfg.iforest_contamination,
                },
            ),
        )
        dist_result = results["dist"]
        missing_result = results["missing"]
        corr_result = results.get("corr")
        outlier_result = results.get("outlier")
        target_result = results.get("target")

        # Charts
        renderer = ChartRenderer(
            out_dir, fmt=cfg.chart_format, dpi=cfg.chart_dpi, theme=cfg.theme
        )
        chart_paths: dict[str, Path] = {}

        def _render(
            fn: Callable[..., dict[str, Path]], *args: Any, **kwargs: Any
        ) -> dict[str, Path]:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return fn(*args, **kwargs)

        dist_fn = renderer.distribution_charts
        chart_paths.update(steps.run(
            "Render distribution charts", lambda: _render(dist_fn, df, dist_result),
        ))
        if corr_result is not None:
            corr_fn = renderer.correlation_charts
            chart_paths.update(steps.run(
                "Render correlation charts",
                lambda: _render(corr_fn, corr_result, max_cols=cfg.max_pairplot_cols),
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
    output_panel(output_items)


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
        str | None, typer.Option("--target", help="Target column for Key Insights section")
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
