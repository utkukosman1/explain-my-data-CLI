from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from emd.schema.contract import SchemaContract


@dataclass
class Violation:
    column: str  # "__global__" for dataset-level checks
    check: str
    expected: str
    actual: str
    severity: str  # "error" | "warning"


@dataclass
class ValidationResult:
    violations: list[Violation] = field(default_factory=list)
    passed: bool = True
    has_warnings: bool = False

    def add(self, v: Violation) -> None:
        self.violations.append(v)
        if v.severity == "error":
            self.passed = False
        if v.severity == "warning":
            self.has_warnings = True


def _infer_dtype(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    return "categorical"


class SchemaValidator:
    @classmethod
    def validate(
        cls, df: pd.DataFrame, contract: SchemaContract, strict: bool = False
    ) -> ValidationResult:
        result = ValidationResult()

        # Step 1 — global min_rows
        min_rows = contract.global_rules.min_rows
        if min_rows is not None and len(df) < min_rows:
            result.add(Violation(
                    column="__global__",
                    check="min_rows",
                    expected=f">= {contract.global_rules.min_rows}",
                    actual=str(len(df)),
                    severity="error",
                ))

        # Step 2 — global max_duplicate_pct
        if contract.global_rules.max_duplicate_pct is not None and len(df) > 0:
            actual_dup_pct = df.duplicated().mean() * 100
            if actual_dup_pct > contract.global_rules.max_duplicate_pct:
                result.add(Violation(
                    column="__global__",
                    check="max_duplicate_pct",
                    expected=f"<= {contract.global_rules.max_duplicate_pct}%",
                    actual=f"{actual_dup_pct:.1f}%",
                    severity="error",
                ))

        # Step 3 — required columns present
        for col, rule in contract.columns.items():
            if rule.required and col not in df.columns:
                result.add(Violation(
                    column=col,
                    check="required",
                    expected="present",
                    actual="missing",
                    severity="error",
                ))

        # Step 4 — extra columns
        if contract.global_rules.extra_columns != "ignore":
            defined = set(contract.columns.keys())
            extras = [c for c in df.columns if c not in defined]
            sev = "error" if contract.global_rules.extra_columns == "fail" else "warning"
            for extra in extras:
                result.add(Violation(
                    column=extra,
                    check="extra_column",
                    expected="not present",
                    actual="present",
                    severity=sev,
                ))

        # Step 5 — per-column checks
        for col, rule in contract.columns.items():
            if col not in df.columns:
                continue  # already flagged in step 3

            series = df[col]
            actual_dtype = _infer_dtype(series)

            # 5a dtype
            if rule.dtype != "any" and actual_dtype != rule.dtype:
                result.add(Violation(
                    column=col,
                    check="dtype",
                    expected=rule.dtype,
                    actual=actual_dtype,
                    severity="error",
                ))
                continue  # skip further checks — they'd be meaningless

            # 5b max_missing_pct
            if rule.max_missing_pct is not None:
                actual_pct = series.isna().mean() * 100
                if actual_pct > rule.max_missing_pct:
                    result.add(Violation(
                        column=col,
                        check="max_missing_pct",
                        expected=f"<= {rule.max_missing_pct}%",
                        actual=f"{actual_pct:.1f}%",
                        severity="error",
                    ))

            # 5c min / max (numeric only)
            if rule.dtype == "numeric":
                non_null = series.dropna()
                if len(non_null) > 0:
                    if rule.min is not None:
                        actual_min = float(non_null.min())
                        if actual_min < rule.min:
                            result.add(Violation(
                                column=col,
                                check="min",
                                expected=f">= {rule.min}",
                                actual=str(actual_min),
                                severity="error",
                            ))
                    if rule.max is not None:
                        actual_max = float(non_null.max())
                        if actual_max > rule.max:
                            result.add(Violation(
                                column=col,
                                check="max",
                                expected=f"<= {rule.max}",
                                actual=str(actual_max),
                                severity="error",
                            ))

            # 5d allowed_values (categorical only, warning)
            if rule.dtype == "categorical" and rule.allowed_values is not None:
                actual_values = set(series.dropna().astype(str).unique())
                unexpected = actual_values - set(rule.allowed_values)
                if unexpected:
                    result.add(Violation(
                        column=col,
                        check="allowed_values",
                        expected=f"subset of {sorted(rule.allowed_values)}",
                        actual=f"unexpected: {sorted(unexpected)}",
                        severity="warning",
                    ))

        # Step 6 — strict mode: promote all warnings to errors
        if strict and result.has_warnings:
            for v in result.violations:
                if v.severity == "warning":
                    v.severity = "error"
                    result.passed = False
            result.has_warnings = False

        return result
