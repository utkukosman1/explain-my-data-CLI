from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from emd import __version__
from emd.analysis.correlation import CorrelationResult
from emd.analysis.distribution import DistributionResult
from emd.analysis.missing import MissingResult
from emd.analysis.outlier import OutlierResult
from emd.quality.checker import QualityReport


class MarkdownReportGenerator:
    def generate(
        self,
        df: pd.DataFrame,
        quality_report: QualityReport,
        dist_result: DistributionResult,
        corr_result: CorrelationResult | None,
        missing_result: MissingResult,
        outlier_result: OutlierResult | None,
        chart_paths: dict[str, Path],
        output_dir: Path,
        source_name: str,
    ) -> Path:
        lines: list[str] = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows, cols = df.shape

        lines += [
            f"# EDA Report — {source_name}",
            "",
            f"**Generated:** {now}  |  **Rows:** {rows:,}  |  **Columns:** {cols}  |  **emd version:** {__version__}",
            "",
            "---",
            "",
            "## Table of Contents",
            "1. [Data Quality Summary](#1-data-quality-summary)",
            "2. [Dataset Overview](#2-dataset-overview)",
            "3. [Distribution Analysis](#3-distribution-analysis)",
            "4. [Correlation Analysis](#4-correlation-analysis)",
            "5. [Missing Value Analysis](#5-missing-value-analysis)",
            "6. [Outlier Detection](#6-outlier-detection)",
            "7. [Appendix](#7-appendix)",
            "",
            "---",
            "",
        ]

        lines += self._quality_section(quality_report)
        lines += self._overview_section(df)
        lines += self._distribution_section(df, dist_result, chart_paths)
        lines += self._correlation_section(corr_result, chart_paths)
        lines += self._missing_section(missing_result, chart_paths)
        lines += self._outlier_section(outlier_result, chart_paths)
        lines += self._appendix_section(dist_result)

        report_path = output_dir / "report.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _quality_section(self, qr: QualityReport) -> list[str]:
        lines = [
            "## 1. Data Quality Summary",
            "",
            f"> **Quality gate result: {qr.status}**",
            "",
        ]
        if not qr.issues:
            lines += ["> No issues detected.", ""]
        else:
            lines += [
                "| Check | Severity | Result | Recommendation |",
                "|:------|:---------|:-------|:---------------|",
            ]
            for issue in qr.issues:
                lines.append(
                    f"| {issue.check} | {issue.severity.value} | {issue.result} | {issue.recommendation} |"
                )
            lines.append("")
        lines += ["---", ""]
        return lines

    def _overview_section(self, df: pd.DataFrame) -> list[str]:
        lines = [
            "## 2. Dataset Overview",
            "",
            f"- **Rows:** {df.shape[0]:,}",
            f"- **Columns:** {df.shape[1]}",
            f"- **Memory usage:** {df.memory_usage(deep=True).sum() / 1024:.1f} KB",
            "",
            "| Column | Dtype | Non-Null | Null % |",
            "|:-------|:------|:---------|:-------|",
        ]
        for col in df.columns:
            dtype = str(df[col].dtype)
            non_null = int(df[col].notna().sum())
            null_pct = df[col].isna().mean() * 100
            lines.append(f"| {col} | {dtype} | {non_null:,} | {null_pct:.2f}% |")
        lines += ["", "---", ""]
        return lines

    def _distribution_section(
        self, df: pd.DataFrame, result: DistributionResult, chart_paths: dict[str, Path]
    ) -> list[str]:
        lines = [
            "## 3. Distribution Analysis",
            "",
            "### 3.1 Numeric Columns",
            "",
        ]

        if result.numeric:
            lines += [
                "| Column | Count | Null% | Mean | Median | Std | Skew | Kurt | Min | Max | Normality p |",
                "|:-------|------:|------:|-----:|-------:|----:|-----:|-----:|----:|----:|------------:|",
            ]
            for s in result.numeric:
                pval = f"{s.normality_pvalue:.4f}" if s.normality_pvalue is not None else "N/A"
                lines.append(
                    f"| {s.name} | {s.count:,} | {s.null_pct:.2%} "
                    f"| {_fmt(s.mean)} | {_fmt(s.median)} | {_fmt(s.std)} "
                    f"| {_fmt(s.skewness)} | {_fmt(s.excess_kurtosis)} "
                    f"| {_fmt(s.min)} | {_fmt(s.max)} | {pval} |"
                )
            lines.append("")

            for s in result.numeric:
                lines += [f"#### {s.name}", ""]
                if f"dist:{s.name}" in chart_paths:
                    rel = _rel_path(chart_paths[f"dist:{s.name}"])
                    lines += [f"![Distribution of {s.name}]({rel})", ""]
                lines += [
                    f"- **Mean:** {_fmt(s.mean)}  |  **Std:** {_fmt(s.std)}  |  **CV:** {_fmt(s.cv) if s.cv else 'N/A'}",
                    f"- **Skewness:** {_fmt(s.skewness)}  |  **Excess Kurtosis:** {_fmt(s.excess_kurtosis)}",
                    f"- **Normality test ({s.normality_test}):** p = {_fmt(s.normality_pvalue) if s.normality_pvalue is not None else 'N/A'}",
                    "",
                ]
        else:
            lines += ["> No numeric columns found.", ""]

        lines += ["### 3.2 Categorical Columns", ""]
        if result.categorical:
            lines += [
                "| Column | Count | Null% | Unique | Mode | Mode Freq | Entropy |",
                "|:-------|------:|------:|-------:|:-----|----------:|--------:|",
            ]
            for s in result.categorical:
                lines.append(
                    f"| {s.name} | {s.count:,} | {s.null_pct:.2%} | {s.unique_count} "
                    f"| {s.mode or 'N/A'} | {s.mode_frequency} | {s.entropy:.3f} |"
                )
            lines.append("")

            for s in result.categorical:
                if f"cat:{s.name}" in chart_paths:
                    rel = _rel_path(chart_paths[f"cat:{s.name}"])
                    lines += [f"#### {s.name}", "", f"![Top values — {s.name}]({rel})", ""]
        else:
            lines += ["> No categorical columns found.", ""]

        lines += ["---", ""]
        return lines

    def _correlation_section(
        self, result: CorrelationResult | None, chart_paths: dict[str, Path]
    ) -> list[str]:
        lines = ["## 4. Correlation Analysis", ""]
        if result is None:
            lines += ["> Correlation analysis was skipped.", "", "---", ""]
            return lines

        for label in ["pearson", "spearman"]:
            key = f"corr_{label}"
            if key in chart_paths:
                rel = _rel_path(chart_paths[key])
                lines += [f"### {label.capitalize()} Correlation", "", f"![{label} heatmap]({rel})", ""]

        if result.strong_pairs:
            lines += [
                "### Strongest Correlations (|r| ≥ 0.7)",
                "",
                "| Column A | Column B | Pearson r | Type |",
                "|:---------|:---------|----------:|:-----|",
            ]
            for col_a, col_b, r, label in result.strong_pairs[:20]:
                lines.append(f"| {col_a} | {col_b} | {r:.4f} | {label} |")
            lines.append("")
            if "corr_top" in chart_paths:
                rel = _rel_path(chart_paths["corr_top"])
                lines += [f"![Top correlations]({rel})", ""]

        if result.vif:
            lines += [
                "### Variance Inflation Factors (VIF)",
                "",
                "| Column | VIF |",
                "|:-------|----:|",
            ]
            for col, v in sorted(result.vif.items(), key=lambda x: -x[1]):
                flag = " ⚠️" if v > 10 else ""
                lines.append(f"| {col} | {v:.2f}{flag} |")
            lines.append("")

        lines += ["---", ""]
        return lines

    def _missing_section(
        self, result: MissingResult, chart_paths: dict[str, Path]
    ) -> list[str]:
        lines = [
            "## 5. Missing Value Analysis",
            "",
            f"- **Total cells:** {result.total_cells:,}",
            f"- **Total missing:** {result.total_missing:,} ({result.global_missing_pct:.2%})",
            f"- **Complete rows:** {result.complete_rows:,} ({result.complete_rows_pct:.2%})",
            "",
        ]

        cols_with_missing = [c for c in result.columns if c.missing_count > 0]
        if cols_with_missing:
            lines += [
                "| Column | Missing | Missing % | Present |",
                "|:-------|--------:|----------:|--------:|",
            ]
            for c in sorted(cols_with_missing, key=lambda x: -x.missing_pct):
                lines.append(
                    f"| {c.name} | {c.missing_count:,} | {c.missing_pct:.2%} | {c.present_count:,} |"
                )
            lines.append("")
            if "missing_bar" in chart_paths:
                rel = _rel_path(chart_paths["missing_bar"])
                lines += [f"![Missing values bar chart]({rel})", ""]
        else:
            lines += ["> No missing values detected.", ""]

        if result.patterns:
            lines += [
                "### Top Missingness Patterns",
                "",
                "| Pattern | Row count | Row % |",
                "|:--------|----------:|------:|",
            ]
            for p in result.patterns[:10]:
                pattern_str = ", ".join(f"{k}" for k, v in p.pattern.items() if v)
                lines.append(f"| {pattern_str} | {p.row_count:,} | {p.row_pct:.2%} |")
            lines.append("")

        if result.correlated_pairs:
            lines += [
                "### Correlated Missingness Pairs (P ≥ 0.5)",
                "",
                "| Column A | Column B | P(both missing) |",
                "|:---------|:---------|----------------:|",
            ]
            for a, b, p in result.correlated_pairs[:10]:
                lines.append(f"| {a} | {b} | {p:.2%} |")
            lines.append("")

        lines += ["---", ""]
        return lines

    def _outlier_section(
        self, result: OutlierResult | None, chart_paths: dict[str, Path]
    ) -> list[str]:
        lines = ["## 6. Outlier Detection", ""]
        if result is None:
            lines += ["> Outlier detection was skipped.", "", "---", ""]
            return lines

        lines += [
            f"**Methods used:** {', '.join(result.methods_used)}",
            "",
            "| Column | IQR | IQR% | IQR Extreme | Z-score | Modified Z |",
            "|:-------|----:|-----:|------------:|--------:|-----------:|",
        ]
        for c in result.columns:
            lines.append(
                f"| {c.name} | {c.iqr_count} | {c.iqr_pct:.2%} | {c.iqr_extreme_count} "
                f"| {c.zscore_count} | {c.mzscore_count} |"
            )
        lines.append("")

        if "outlier_comparison" in chart_paths:
            rel = _rel_path(chart_paths["outlier_comparison"])
            lines += [f"![Outlier method comparison]({rel})", ""]

        for c in result.columns:
            if f"outlier:{c.name}" in chart_paths:
                rel = _rel_path(chart_paths[f"outlier:{c.name}"])
                lines += [f"#### {c.name}", "", f"![Outliers — {c.name}]({rel})", ""]

        lines += ["---", ""]
        return lines

    def _appendix_section(self, result: DistributionResult) -> list[str]:
        lines = ["## 7. Appendix", "", "### Full Percentile Table (Numeric Columns)", ""]
        if result.numeric:
            lines += [
                "| Column | p5 | p25 | p50 | p75 | p95 | IQR |",
                "|:-------|---:|----:|----:|----:|----:|----:|",
            ]
            for s in result.numeric:
                lines.append(
                    f"| {s.name} | {_fmt(s.p5)} | {_fmt(s.p25)} | {_fmt(s.p50)} "
                    f"| {_fmt(s.p75)} | {_fmt(s.p95)} | {_fmt(s.iqr)} |"
                )
        lines.append("")
        return lines

    # ------------------------------------------------------------------
    # JSON output
    # ------------------------------------------------------------------
    def write_json(
        self,
        quality_report: QualityReport,
        dist_result: DistributionResult,
        corr_result: CorrelationResult | None,
        missing_result: MissingResult,
        outlier_result: OutlierResult | None,
        output_dir: Path,
    ) -> Path:
        import dataclasses

        def _safe(obj: object) -> object:
            if isinstance(obj, float):
                import math
                return None if math.isnan(obj) or math.isinf(obj) else obj
            if isinstance(obj, pd.DataFrame):
                return obj.to_dict()
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return {k: _safe(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, list):
                return [_safe(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _safe(v) for k, v in obj.items()}
            if isinstance(obj, tuple):
                return [_safe(i) for i in obj]
            return obj

        payload = {
            "quality": _safe(quality_report),
            "distribution": _safe(dist_result),
            "missing": _safe(missing_result),
        }
        if corr_result is not None:
            payload["correlation"] = {
                "pearson": corr_result.pearson.to_dict() if corr_result.pearson is not None else None,
                "spearman": corr_result.spearman.to_dict() if corr_result.spearman is not None else None,
                "strong_pairs": _safe(corr_result.strong_pairs),
                "vif": corr_result.vif,
            }
        if outlier_result is not None:
            payload["outlier"] = _safe(outlier_result)

        out_path = output_dir / "analysis_results.json"
        out_path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
        return out_path


def _fmt(val: float | None, sig: int = 4) -> str:
    if val is None:
        return "N/A"
    import math
    if math.isnan(val) or math.isinf(val):
        return "N/A"
    if val == 0:
        return "0"
    if abs(val) >= 1000 or (abs(val) < 0.001 and val != 0):
        return f"{val:.{sig}g}"
    return f"{val:.{sig}g}"



def _rel_path(p: Path) -> str:
    parts = p.parts
    try:
        idx = parts.index("charts")
        return "/".join(parts[idx:])
    except ValueError:
        return str(p)
