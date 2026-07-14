from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from emd.analysis import (
    CorrelationAnalyzer,
    DistributionAnalyzer,
    DoctorAnalyzer,
    DoctorResult,
    DoctorSeverity,
    MissingAnalyzer,
    OutlierAnalyzer,
    TargetAnalyzer,
)
from emd.analysis.doctor import (
    CAT_COMPLETENESS,
    CATEGORY_CAP,
    DoctorFinding,
    compute_health_score,
    health_band,
)
from emd.quality import QualityChecker


def diagnose(df: pd.DataFrame, target: str | None = None) -> DoctorResult:
    dist = DistributionAnalyzer().analyze(df)
    missing = MissingAnalyzer().analyze(df)
    corr = CorrelationAnalyzer().analyze(df)
    outlier = OutlierAnalyzer().analyze(df)
    quality = QualityChecker().check(df, no_quality_gate=True)
    target_result = TargetAnalyzer().analyze(df, target) if target else None
    return DoctorAnalyzer().diagnose(
        df,
        dist_result=dist,
        missing_result=missing,
        corr_result=corr,
        outlier_result=outlier,
        quality_report=quality,
        target_result=target_result,
    )


def checks(result: DoctorResult, severity: DoctorSeverity | None = None) -> list[str]:
    findings = result.findings if severity is None else result.by_severity(severity)
    return [f.check for f in findings]


def test_clean_dataset_scores_high(simple_df: pd.DataFrame) -> None:
    result = diagnose(simple_df)
    assert result.n_critical == 0
    assert result.score >= 90
    assert result.band == "Excellent"


def test_empty_column_is_critical() -> None:
    df = pd.DataFrame({"a": range(100), "b": [np.nan] * 100})
    result = diagnose(df)
    assert "Empty column" in checks(result, DoctorSeverity.CRITICAL)


def test_severe_missingness_is_critical() -> None:
    df = pd.DataFrame({"a": range(100), "b": [1.0] * 40 + [np.nan] * 60})
    result = diagnose(df)
    assert "Severe missingness" in checks(result, DoctorSeverity.CRITICAL)


def test_high_missingness_is_warning() -> None:
    df = pd.DataFrame({"a": range(100), "b": [1.0, 2.0, 3.0, 4.0] * 20 + [np.nan] * 20})
    result = diagnose(df)
    assert "High missingness" in checks(result, DoctorSeverity.WARNING)


def test_constant_column_is_critical() -> None:
    df = pd.DataFrame({"a": range(100), "b": [7] * 100})
    result = diagnose(df)
    assert "Constant column" in checks(result, DoctorSeverity.CRITICAL)


def test_duplicate_columns_are_critical() -> None:
    rng = np.random.default_rng(1)
    values = rng.normal(0, 1, 100)
    df = pd.DataFrame({"a": values, "b": values, "c": rng.uniform(0, 1, 100)})
    result = diagnose(df)
    critical = [f for f in result.by_severity(DoctorSeverity.CRITICAL)
                if f.check == "Duplicate columns"]
    assert len(critical) == 1
    assert set(critical[0].columns) == {"a", "b"}


def test_quality_report_findings_propagate() -> None:
    """doctor.py maps QualityChecker issues into findings by matching `issue.check`
    strings (e.g. "Mixed types: <col>", "All-object dtypes", "Special chars in
    column names"). That string coupling has no compiler check, so this test
    pins the three propagated checks — if QualityChecker's wording ever changes,
    this fails loudly instead of doctor.py silently dropping the finding."""
    df = pd.DataFrame({
        "a!": range(100),
        "mixed": [str(i) for i in range(70)] + ["not_a_number"] * 30,
    })
    result = diagnose(df)
    found_checks = checks(result)
    assert "Special characters in column names" in found_checks
    assert "Mixed types" in found_checks

    # pandas 3 infers plain string columns as dtype "str", not "object" — the
    # "All-object dtypes" quality check (and this propagation) only fires for
    # genuine object dtype, so force it explicitly rather than via a literal.
    all_object_df = pd.DataFrame(
        {"x": ["a"] * 10, "y": ["c"] * 10}, dtype=object
    )
    result = diagnose(all_object_df)
    assert "All-text columns" in checks(result)


def test_near_constant_column_is_warning() -> None:
    df = pd.DataFrame({"a": range(100), "b": ["x"] * 99 + ["y"]})
    result = diagnose(df)
    assert "Near-constant column" in checks(result, DoctorSeverity.WARNING)


def test_numeric_stored_as_text_is_warning() -> None:
    rng = np.random.default_rng(2)
    df = pd.DataFrame({
        "a": rng.normal(0, 1, 100),
        "b": [str(v) for v in rng.integers(0, 5, 100)],
    })
    result = diagnose(df)
    assert "Numeric stored as text" in checks(result, DoctorSeverity.WARNING)


def test_dates_stored_as_text_is_info() -> None:
    dates = pd.date_range("2024-01-01", periods=100).strftime("%Y-%m-%d").tolist()
    df = pd.DataFrame({"a": range(100), "b": dates})
    result = diagnose(df)
    assert "Dates stored as text" in checks(result, DoctorSeverity.INFO)


def test_disguised_missing_values_is_warning() -> None:
    df = pd.DataFrame({"a": range(100), "b": ["x", "y", "NA", "?", "z"] * 20})
    result = diagnose(df)
    finding = next(
        f for f in result.by_severity(DoctorSeverity.WARNING)
        if f.check == "Disguised missing values"
    )
    assert finding.columns == ["b"]
    assert "40" in finding.message  # 20 x "NA" + 20 x "?"


def test_inconsistent_category_labels_is_warning() -> None:
    df = pd.DataFrame({"a": range(100), "b": ["Male", "male", "Female", "female "] * 25})
    result = diagnose(df)
    assert "Inconsistent category labels" in checks(result, DoctorSeverity.WARNING)


def test_duplicate_rows_severity_scales() -> None:
    base = {"a": 1, "b": "x"}
    df = pd.DataFrame([base] * 40 + [{"a": i, "b": "y"} for i in range(60)])
    result = diagnose(df)
    dup = next(f for f in result.findings if f.check == "Duplicate rows")
    assert dup.severity == DoctorSeverity.CRITICAL  # 39% duplicates

    df_few = pd.DataFrame(
        [{"a": i, "b": "y"} for i in range(998)] + [{"a": 0, "b": "y"}] * 2
    )
    result_few = diagnose(df_few)
    dup_few = next(f for f in result_few.findings if f.check == "Duplicate rows")
    assert dup_few.severity == DoctorSeverity.INFO  # 0.2% duplicates


def test_identifier_column_is_warning() -> None:
    df = pd.DataFrame({"id": range(1, 201), "value": np.random.default_rng(3).normal(0, 1, 200)})
    result = diagnose(df)
    finding = next(
        f for f in result.by_severity(DoctorSeverity.WARNING) if f.check == "Identifier column"
    )
    assert finding.columns == ["id"]


def test_few_rows_per_column_is_warning() -> None:
    rng = np.random.default_rng(4)
    df = pd.DataFrame({f"c{i}": rng.normal(0, 1, 10) for i in range(8)})
    result = diagnose(df)
    assert "Few rows per column" in checks(result, DoctorSeverity.WARNING)


def test_target_leakage_is_critical() -> None:
    rng = np.random.default_rng(5)
    x = rng.normal(0, 1, 100)
    df = pd.DataFrame({"x": x, "y": 2 * x, "noise": rng.uniform(0, 1, 100)})
    result = diagnose(df, target="y")
    finding = next(
        f for f in result.by_severity(DoctorSeverity.CRITICAL)
        if f.check == "Possible target leakage"
    )
    assert finding.columns == ["x"]


def test_class_imbalance_is_warning() -> None:
    rng = np.random.default_rng(6)
    df = pd.DataFrame({
        "x": rng.normal(0, 1, 200),
        "label": ["A"] * 190 + ["B"] * 10,
    })
    result = diagnose(df, target="label")
    finding = next(
        f for f in result.by_severity(DoctorSeverity.WARNING) if f.check == "Class imbalance"
    )
    assert "'B'" in finding.message


def test_no_target_checks_without_target(simple_df: pd.DataFrame) -> None:
    result = diagnose(simple_df)
    assert all(f.category != "Target Risks" for f in result.findings)


def test_score_is_deterministic() -> None:
    df = pd.DataFrame({
        "a": range(100),
        "b": [np.nan] * 60 + list(range(40)),
        "c": ["x"] * 99 + ["y"],
    })
    first = diagnose(df)
    second = diagnose(df)
    assert first.score == second.score
    assert [f.message for f in first.findings] == [f.message for f in second.findings]
    assert first.assessment == second.assessment


def test_findings_sorted_by_severity() -> None:
    df = pd.DataFrame({
        "a": range(100),
        "b": [np.nan] * 100,          # critical
        "c": ["x"] * 99 + ["y"],      # warning
    })
    result = diagnose(df)
    order = {DoctorSeverity.CRITICAL: 0, DoctorSeverity.WARNING: 1, DoctorSeverity.INFO: 2}
    ranks = [order[f.severity] for f in result.findings]
    assert ranks == sorted(ranks)


def test_category_penalty_is_capped() -> None:
    findings = [
        DoctorFinding(
            check="Empty column", category=CAT_COMPLETENESS,
            severity=DoctorSeverity.CRITICAL, columns=[f"c{i}"], message="x",
        )
        for i in range(10)
    ]
    score, capped = compute_health_score(findings)
    assert capped[CAT_COMPLETENESS] == CATEGORY_CAP
    assert score == 100 - CATEGORY_CAP


def test_info_findings_do_not_deduct() -> None:
    findings = [
        DoctorFinding(
            check="Correlated missingness", category=CAT_COMPLETENESS,
            severity=DoctorSeverity.INFO, columns=[], message="x",
        )
    ]
    score, capped = compute_health_score(findings)
    assert score == 100
    assert capped == {}


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (100, "Excellent"), (90, "Excellent"),
        (89, "Good"), (75, "Good"),
        (74, "Fair"), (60, "Fair"),
        (59, "Poor"), (40, "Poor"),
        (39, "Critical"), (0, "Critical"),
    ],
)
def test_health_bands(score: int, band: str) -> None:
    assert health_band(score) == band


def test_assessment_mentions_counts_and_categories() -> None:
    df = pd.DataFrame({"a": range(100), "b": [np.nan] * 100})
    result = diagnose(df)
    assert "critical issue" in result.assessment
    assert "Completeness" in result.assessment


def test_doctor_report_file(tmp_path: Path) -> None:
    from emd.report import MarkdownReportGenerator

    df = pd.DataFrame({
        "a": range(100),
        "b": [np.nan] * 60 + list(range(40)),
        "c": ["x"] * 99 + ["y"],
    })
    result = diagnose(df)
    path = MarkdownReportGenerator().generate_doctor_report(
        df=df, result=result, output_dir=tmp_path, source_name="test.csv",
    )
    assert path.name == "doctor-report.md"
    content = path.read_text(encoding="utf-8")
    assert "## 1. Dataset Health Score" in content
    assert "## 2. Overall Assessment" in content
    assert "## 3. Critical Issues" in content
    assert "## 4. Warnings" in content
    assert "## 5. Information" in content
    assert "## 6. Output" in content
    assert f"**{result.score} / 100 — {result.band}**" in content
