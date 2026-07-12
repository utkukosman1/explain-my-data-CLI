from __future__ import annotations

import tempfile
import shutil
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from emd.analysis import (
    CorrelationAnalyzer,
    DistributionAnalyzer,
    MissingAnalyzer,
    OutlierAnalyzer,
    TargetAnalyzer,
)
from emd.analysis.drift import DriftAnalyzer
from emd.loader import CSVLoader, XLSXLoader
from emd.quality import QualityChecker

from .serializer import (
    categorical_bars,
    corr_heatmap,
    drift_overlay,
    missing_bars,
    numeric_histogram,
    outlier_bars,
    safe,
)


def _load(path: Path, sheet: str | None, parse_dates: list[str]) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        return XLSXLoader().load(path, sheet=sheet, parse_dates=parse_dates)
    return CSVLoader().load(path, parse_dates=parse_dates)


def run_analyze(
    job_id: str,
    file_bytes: bytes,
    filename: str,
    options: dict[str, Any],
    progress_cb: Callable[[str, int], None],
) -> dict[str, Any]:
    """
    Run full EDA analysis on uploaded file bytes.
    progress_cb(step_label, percent) is called at each step so the caller can
    update the job store without any asyncio dependency.
    Returns a JSON-serializable result dict.
    """
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        progress_cb("Loading data", 5)
        parse_dates = [c.strip() for c in options.get("parse_dates", "").split(",") if c.strip()]
        drop_cols = [c.strip() for c in options.get("drop_cols", "").split(",") if c.strip()]
        df = _load(tmp_path, options.get("sheet"), parse_dates)

        if drop_cols:
            df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

        sample_size = options.get("sample_size")
        if sample_size and len(df) > sample_size:
            df = df.sample(n=sample_size, random_state=42)

        progress_cb("Quality check", 15)
        quality_report = QualityChecker().check(df, no_quality_gate=True)

        progress_cb("Distribution analysis", 30)
        dist_result = DistributionAnalyzer().analyze(df)

        progress_cb("Missing value analysis", 45)
        missing_result = MissingAnalyzer().analyze(df)

        corr_result = None
        if not options.get("skip_correlation", False):
            progress_cb("Correlation analysis", 60)
            corr_result = CorrelationAnalyzer().analyze(df)

        outlier_result = None
        if not options.get("skip_outlier", False):
            progress_cb("Outlier detection", 75)
            outlier_result = OutlierAnalyzer(
                use_iforest=options.get("use_iforest", False)
            ).analyze(df)

        target_result = None
        target_col = options.get("target")
        if target_col and target_col in df.columns:
            progress_cb(f"Target analysis ({target_col})", 85)
            target_result = TargetAnalyzer().analyze(df, target_col)

        progress_cb("Building response", 95)
        result = _build_result(
            df=df,
            filename=filename,
            quality_report=quality_report,
            dist_result=dist_result,
            missing_result=missing_result,
            corr_result=corr_result,
            outlier_result=outlier_result,
            target_result=target_result,
        )
        result["_markdown"] = _generate_markdown(
            df=df,
            filename=filename,
            quality_report=quality_report,
            dist_result=dist_result,
            corr_result=corr_result,
            missing_result=missing_result,
            outlier_result=outlier_result,
            target_result=target_result,
        )
        return result
    finally:
        tmp_path.unlink(missing_ok=True)


def run_compare(
    job_id: str,
    ref_bytes: bytes,
    ref_name: str,
    cur_bytes: bytes,
    cur_name: str,
    options: dict[str, Any],
    progress_cb: Callable[[str, int], None],
) -> dict[str, Any]:
    """Run drift analysis between two uploaded files."""
    ref_suffix = Path(ref_name).suffix.lower()
    cur_suffix = Path(cur_name).suffix.lower()

    with tempfile.NamedTemporaryFile(suffix=ref_suffix, delete=False) as f:
        f.write(ref_bytes)
        ref_path = Path(f.name)
    with tempfile.NamedTemporaryFile(suffix=cur_suffix, delete=False) as f:
        f.write(cur_bytes)
        cur_path = Path(f.name)

    try:
        progress_cb("Loading reference dataset", 10)
        df_ref = _load(ref_path, None, [])
        progress_cb("Loading current dataset", 25)
        df_cur = _load(cur_path, None, [])

        threshold = float(options.get("threshold", 0.2))
        progress_cb("Analysing drift", 55)
        drift_result = DriftAnalyzer(psi_threshold=threshold).analyze(df_ref, df_cur)

        progress_cb("Building response", 90)
        result = _build_drift_result(df_ref=df_ref, df_cur=df_cur, ref_name=ref_name, cur_name=cur_name, drift_result=drift_result)
        return result
    finally:
        ref_path.unlink(missing_ok=True)
        cur_path.unlink(missing_ok=True)


def run_check(
    file_bytes: bytes,
    filename: str,
) -> dict[str, Any]:
    """Quick synchronous quality check — no job needed."""
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)
    try:
        df = _load(tmp_path, None, [])
        qr = QualityChecker().check(df, no_quality_gate=True)
        return {
            "filename": filename,
            "shape": {"rows": df.shape[0], "cols": df.shape[1]},
            "quality": safe(qr),
        }
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_result(
    df: pd.DataFrame,
    filename: str,
    quality_report: Any,
    dist_result: Any,
    missing_result: Any,
    corr_result: Any | None,
    outlier_result: Any | None,
    target_result: Any | None,
) -> dict[str, Any]:
    # Overview
    overview = {
        "filename": filename,
        "rows": df.shape[0],
        "cols": df.shape[1],
        "memory_kb": round(df.memory_usage(deep=True).sum() / 1024, 1),
        "columns": [
            {
                "name": col,
                "dtype": str(df[col].dtype),
                "non_null": int(df[col].notna().sum()),
                "null_pct": round(df[col].isna().mean() * 100, 2),
            }
            for col in df.columns
        ],
    }

    # Distribution with chart data
    numeric_cols = df.select_dtypes(include="number")
    distribution: dict[str, Any] = {
        "numeric": [
            {
                **safe(s),
                "chart_data": numeric_histogram(df[s.name]),
                "box_data": {
                    "min": safe(s.min),
                    "p25": safe(s.p25),
                    "p50": safe(s.p50),
                    "p75": safe(s.p75),
                    "max": safe(s.max),
                    "mean": safe(s.mean),
                },
            }
            for s in dist_result.numeric
        ],
        "categorical": [
            {
                **safe(s),
                "chart_data": categorical_bars(s.top_values),
            }
            for s in dist_result.categorical
        ],
    }

    # Missing
    missing = {
        **safe(missing_result),
        "chart_data": missing_bars(missing_result),
    }

    # Correlation
    correlation: dict[str, Any] | None = None
    if corr_result is not None:
        correlation = {
            "pearson": corr_heatmap(corr_result.pearson),
            "pearson_columns": list(corr_result.pearson.columns) if corr_result.pearson is not None else [],
            "spearman": corr_heatmap(corr_result.spearman),
            "spearman_columns": list(corr_result.spearman.columns) if corr_result.spearman is not None else [],
            "cramers_v": corr_heatmap(corr_result.cramers_v),
            "cramers_v_columns": list(corr_result.cramers_v.columns) if corr_result.cramers_v is not None else [],
            "strong_pairs": [
                {"col_a": a, "col_b": b, "r": safe(r), "label": lbl}
                for a, b, r, lbl in corr_result.strong_pairs
            ],
            "point_biserial": [
                {"num_col": nc, "bin_col": bc, "r": safe(r), "p": safe(p)}
                for nc, bc, r, p in corr_result.point_biserial
            ],
            "vif": {k: safe(v) for k, v in corr_result.vif.items()} if corr_result.vif else None,
            "warnings": corr_result.warnings,
        }

    # Outlier
    outlier: dict[str, Any] | None = None
    if outlier_result is not None:
        outlier = {
            **safe(outlier_result),
            "chart_data": outlier_bars(outlier_result),
        }

    # Target
    target: dict[str, Any] | None = None
    if target_result is not None:
        target = safe(target_result)

    return {
        "overview": overview,
        "quality": safe(quality_report),
        "distribution": distribution,
        "missing": missing,
        "correlation": correlation,
        "outlier": outlier,
        "target": target,
    }


def _build_drift_result(
    df_ref: pd.DataFrame,
    df_cur: pd.DataFrame,
    ref_name: str,
    cur_name: str,
    drift_result: Any,
) -> dict[str, Any]:
    # Build overlay chart data for numeric drifted columns
    chart_data: dict[str, list[dict[str, Any]]] = {}
    for col_drift in drift_result.columns:
        if col_drift.col_type == "numeric" and col_drift.drift_detected:
            if col_drift.name in df_ref.columns and col_drift.name in df_cur.columns:
                chart_data[col_drift.name] = drift_overlay(
                    col_drift.name, df_ref[col_drift.name], df_cur[col_drift.name]
                )

    return {
        "ref_name": ref_name,
        "cur_name": cur_name,
        "summary": {
            "reference_shape": list(drift_result.reference_shape),
            "current_shape": list(drift_result.current_shape),
            "drifted_count": len(drift_result.drifted_columns),
            "total_columns": len(drift_result.columns),
            "drift_fraction": round(drift_result.drift_fraction, 4),
            "overall_drift": drift_result.overall_drift,
            "missing_in_current": drift_result.missing_in_current,
            "new_in_current": drift_result.new_in_current,
            "psi_threshold": drift_result.psi_threshold,
        },
        "columns": [
            {
                "name": c.name,
                "col_type": c.col_type,
                "psi": safe(c.psi),
                "ks_pvalue": safe(c.ks_pvalue),
                "mean_shift_pct": safe(c.mean_shift_pct),
                "chi2_pvalue": safe(c.chi2_pvalue),
                "drift_detected": c.drift_detected,
                "drift_severity": c.drift_severity,
                "mean_ref": safe(c.mean_a),
                "mean_cur": safe(c.mean_b),
            }
            for c in sorted(drift_result.columns, key=lambda x: -(x.psi or 0))
        ],
        "drifted_columns": drift_result.drifted_columns,
        "chart_data": chart_data,
    }


def _generate_markdown(
    df: "pd.DataFrame",
    filename: str,
    quality_report: Any,
    dist_result: Any,
    corr_result: Any | None,
    missing_result: Any,
    outlier_result: Any | None,
    target_result: Any | None,
) -> str:
    """Generate the full Markdown report (no charts) and return as string."""
    from emd.report import MarkdownReportGenerator

    tmpdir = Path(tempfile.mkdtemp())
    try:
        report_path = MarkdownReportGenerator().generate(
            df=df,
            quality_report=quality_report,
            dist_result=dist_result,
            corr_result=corr_result,
            missing_result=missing_result,
            outlier_result=outlier_result,
            chart_paths={},
            output_dir=tmpdir,
            source_name=filename,
            target_result=target_result,
        )
        return report_path.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
