from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class Severity(str, Enum):
    FATAL = "FATAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class QualityIssue:
    check: str
    severity: Severity
    result: str
    recommendation: str


@dataclass
class QualityReport:
    issues: list[QualityIssue] = field(default_factory=list)
    passed: bool = True
    has_warnings: bool = False

    @property
    def status(self) -> str:
        if not self.passed:
            return "FAILED"
        if self.has_warnings:
            return "PASSED WITH WARNINGS"
        return "PASSED"

    def add(self, issue: QualityIssue) -> None:
        self.issues.append(issue)
        if issue.severity == Severity.FATAL:
            self.passed = False
        if issue.severity == Severity.WARNING:
            self.has_warnings = True


class DataQualityError(Exception):
    pass


class QualityChecker:
    def check(self, df: pd.DataFrame, no_quality_gate: bool = False) -> QualityReport:
        report = QualityReport()

        self._check_empty(df, report)
        if not report.passed and not no_quality_gate:
            raise DataQualityError(
                f"Data quality FATAL: {report.issues[-1].result}"
            )

        self._check_high_missing_columns(df, report)
        self._check_duplicate_rows(df, report)
        self._check_all_object_dtype(df, report)
        self._check_special_char_columns(df, report)
        self._check_mixed_types(df, report)

        return report

    def _check_empty(self, df: pd.DataFrame, report: QualityReport) -> None:
        if df.shape[0] == 0:
            report.add(QualityIssue(
                check="Empty rows",
                severity=Severity.FATAL,
                result="Dataset has 0 rows",
                recommendation="Verify the file is not empty and the delimiter is correct",
            ))
        if df.shape[1] == 0:
            report.add(QualityIssue(
                check="Empty columns",
                severity=Severity.FATAL,
                result="Dataset has 0 columns",
                recommendation="Check that the file has a valid header row",
            ))

    def _check_high_missing_columns(self, df: pd.DataFrame, report: QualityReport) -> None:
        for col in df.columns:
            pct = df[col].isna().mean()
            if pct > 0.90:
                report.add(QualityIssue(
                    check=f"High missing: {col}",
                    severity=Severity.WARNING,
                    result=f"{pct:.1%} of values are missing in column '{col}'",
                    recommendation=f"Consider dropping or imputing '{col}' before analysis",
                ))

    def _check_duplicate_rows(self, df: pd.DataFrame, report: QualityReport) -> None:
        dup_pct = df.duplicated().mean()
        if dup_pct > 0.50:
            report.add(QualityIssue(
                check="High duplicates",
                severity=Severity.WARNING,
                result=f"{dup_pct:.1%} of rows are exact duplicates ({int(dup_pct * len(df))} rows)",
                recommendation="De-duplicate before analysis to avoid skewed statistics",
            ))

    def _check_all_object_dtype(self, df: pd.DataFrame, report: QualityReport) -> None:
        all_object = all(dtype == object for dtype in df.dtypes)
        if all_object and df.shape[1] > 1:
            report.add(QualityIssue(
                check="All-object dtypes",
                severity=Severity.WARNING,
                result="All columns are dtype=object — numeric parsing may have failed",
                recommendation="Check the delimiter and decimal separator in the source file",
            ))

    def _check_special_char_columns(self, df: pd.DataFrame, report: QualityReport) -> None:
        bad = [c for c in df.columns if any(ch in c for ch in "!@#$%^&*()[]{}<>?/\\|")]
        if bad:
            report.add(QualityIssue(
                check="Special chars in column names",
                severity=Severity.INFO,
                result=f"Columns with special characters: {bad}",
                recommendation="Column names have been stripped of leading/trailing whitespace",
            ))

    def _check_mixed_types(self, df: pd.DataFrame, report: QualityReport) -> None:
        for col in df.select_dtypes(include="object").columns:
            numeric_share = pd.to_numeric(df[col], errors="coerce").notna().mean()
            if 0.01 < numeric_share < 0.99:
                report.add(QualityIssue(
                    check=f"Mixed types: {col}",
                    severity=Severity.WARNING,
                    result=f"Column '{col}' is {numeric_share:.1%} numeric — may be a mixed-type column",
                    recommendation=f"Inspect '{col}' for rogue non-numeric values or encoding issues",
                ))
