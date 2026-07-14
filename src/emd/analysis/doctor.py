from __future__ import annotations

import warnings
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from emd.analysis.correlation import CorrelationResult
from emd.analysis.distribution import (
    CategoricalColumnStats,
    DistributionResult,
    NumericColumnStats,
)
from emd.analysis.missing import MissingResult
from emd.analysis.outlier import OutlierResult
from emd.analysis.target import TargetResult
from emd.quality.checker import QualityReport


class DoctorSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


CAT_STRUCTURE = "Structure"
CAT_COMPLETENESS = "Completeness"
CAT_DUPLICATION = "Duplication"
CAT_TYPE_INTEGRITY = "Type Integrity"
CAT_FEATURE_QUALITY = "Feature Quality"
CAT_REDUNDANCY = "Redundancy"
CAT_TARGET_RISKS = "Target Risks"

CATEGORY_ORDER = [
    CAT_STRUCTURE,
    CAT_COMPLETENESS,
    CAT_DUPLICATION,
    CAT_TYPE_INTEGRITY,
    CAT_FEATURE_QUALITY,
    CAT_REDUNDANCY,
    CAT_TARGET_RISKS,
]

# Health score: start at 100, deduct per finding by severity, cap the total
# deduction per category so wide datasets with many mild findings in one
# dimension score "poor on that dimension" rather than zero overall.
PENALTIES: dict[DoctorSeverity, int] = {
    DoctorSeverity.CRITICAL: 15,
    DoctorSeverity.WARNING: 5,
    DoctorSeverity.INFO: 0,
}
CATEGORY_CAP = 25

_SEVERE_MISSING_PCT = 0.50
_HIGH_MISSING_PCT = 0.10
_DUP_ROWS_CRITICAL_PCT = 0.20
_DUP_ROWS_WARNING_PCT = 0.01
_NEAR_CONSTANT_SHARE = 0.99
_NUMERIC_AS_TEXT_SHARE = 0.99
_DATE_AS_TEXT_SHARE = 0.95
_ID_NUMERIC_UNIQUE_PCT = 0.95
_ID_CATEGORICAL_UNIQUE_PCT = 0.98
_HIGH_CARDINALITY_UNIQUE = 50
_NEAR_DUPLICATE_R = 0.95
_SEVERE_VIF = 10.0
_EXTREME_OUTLIER_PCT = 0.05
_LEAKAGE_SCORE = 0.99
_IMBALANCE_MINORITY_PCT = 0.10
_MIN_ROWS_PER_COLUMN = 5

_MISSING_SENTINELS = frozenset(
    {"", "?", "-", "na", "n/a", "#n/a", "null", "none", "nan", "missing"}
)


@dataclass
class DoctorFinding:
    check: str
    category: str
    severity: DoctorSeverity
    columns: list[str]
    message: str


@dataclass
class DoctorResult:
    findings: list[DoctorFinding]
    score: int
    band: str
    assessment: str
    category_penalties: dict[str, int]  # capped deduction per category

    def by_severity(self, severity: DoctorSeverity) -> list[DoctorFinding]:
        return [f for f in self.findings if f.severity == severity]

    # Computed from `findings` rather than stored, so they can never drift out
    # of sync with the list they summarize.
    @property
    def n_critical(self) -> int:
        return len(self.by_severity(DoctorSeverity.CRITICAL))

    @property
    def n_warning(self) -> int:
        return len(self.by_severity(DoctorSeverity.WARNING))

    @property
    def n_info(self) -> int:
        return len(self.by_severity(DoctorSeverity.INFO))


def compute_health_score(findings: list[DoctorFinding]) -> tuple[int, dict[str, int]]:
    raw: dict[str, int] = {}
    for f in findings:
        raw[f.category] = raw.get(f.category, 0) + PENALTIES[f.severity]
    capped = {cat: min(total, CATEGORY_CAP) for cat, total in raw.items() if total > 0}
    score = max(0, 100 - sum(capped.values()))
    return score, capped


def health_band(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 60:
        return "Fair"
    if score >= 40:
        return "Poor"
    return "Critical"


def _plural(count: int) -> str:
    return "s" if count != 1 else ""


def _build_assessment(
    band: str, n_critical: int, n_warning: int, n_info: int, capped: dict[str, int]
) -> str:
    if n_critical == 0 and n_warning == 0:
        if n_info == 0:
            return f"{band} — no issues detected."
        return (
            f"{band} — no critical issues or warnings; "
            f"{n_info} informational note{_plural(n_info)}."
        )
    parts = []
    if n_critical:
        parts.append(f"{n_critical} critical issue{_plural(n_critical)}")
    if n_warning:
        parts.append(f"{n_warning} warning{_plural(n_warning)}")
    top = sorted(capped.items(), key=lambda item: (-item[1], CATEGORY_ORDER.index(item[0])))[:2]
    cats = " and ".join(cat for cat, _penalty in top)
    return f"{band} — {' and '.join(parts)}, concentrated in {cats}."


class DoctorAnalyzer:
    """Maps existing analyzer results + a set of raw-DataFrame checks into
    severity-ranked findings and a deterministic 0-100 health score.

    Diagnostics only: findings state what is wrong or risky, never what to do
    about it, and never repeat descriptive statistics from the EDA report.
    """

    def diagnose(
        self,
        df: pd.DataFrame,
        dist_result: DistributionResult,
        missing_result: MissingResult,
        corr_result: CorrelationResult | None = None,
        outlier_result: OutlierResult | None = None,
        quality_report: QualityReport | None = None,
        target_result: TargetResult | None = None,
    ) -> DoctorResult:
        findings: list[DoctorFinding] = []
        findings += self._structure(df, quality_report)
        findings += self._completeness(missing_result)
        dup_col_pairs = self._duplicate_column_pairs(df)
        findings += self._duplication(df, dup_col_pairs)
        findings += self._type_integrity(df, quality_report)
        findings += self._feature_quality(df, dist_result, outlier_result)
        findings += self._redundancy(corr_result, dup_col_pairs)
        if target_result is not None:
            findings += self._target_risks(df, target_result)

        sev_order = {DoctorSeverity.CRITICAL: 0, DoctorSeverity.WARNING: 1, DoctorSeverity.INFO: 2}
        findings.sort(key=lambda f: sev_order[f.severity])

        score, capped = compute_health_score(findings)
        band = health_band(score)
        counts = Counter(f.severity for f in findings)

        return DoctorResult(
            findings=findings,
            score=score,
            band=band,
            assessment=_build_assessment(
                band,
                counts[DoctorSeverity.CRITICAL],
                counts[DoctorSeverity.WARNING],
                counts[DoctorSeverity.INFO],
                capped,
            ),
            category_penalties=capped,
        )

    # ------------------------------------------------------------------
    # Structure
    # ------------------------------------------------------------------

    def _structure(
        self, df: pd.DataFrame, quality_report: QualityReport | None
    ) -> list[DoctorFinding]:
        out: list[DoctorFinding] = []
        n_rows, n_cols = df.shape
        if 0 < n_rows < _MIN_ROWS_PER_COLUMN * n_cols:
            out.append(DoctorFinding(
                check="Few rows per column",
                category=CAT_STRUCTURE,
                severity=DoctorSeverity.WARNING,
                columns=[],
                message=(
                    f"Only {n_rows:,} rows for {n_cols} columns — fewer than "
                    f"{_MIN_ROWS_PER_COLUMN} rows per column."
                ),
            ))
        if quality_report is not None:
            for issue in quality_report.issues:
                if issue.check == "Special chars in column names":
                    out.append(DoctorFinding(
                        check="Special characters in column names",
                        category=CAT_STRUCTURE,
                        severity=DoctorSeverity.INFO,
                        columns=[],
                        message=issue.result,
                    ))
        return out

    # ------------------------------------------------------------------
    # Completeness
    # ------------------------------------------------------------------

    def _completeness(self, missing_result: MissingResult) -> list[DoctorFinding]:
        out: list[DoctorFinding] = []
        for col in missing_result.columns:
            if col.missing_pct >= 1.0:
                out.append(DoctorFinding(
                    check="Empty column",
                    category=CAT_COMPLETENESS,
                    severity=DoctorSeverity.CRITICAL,
                    columns=[col.name],
                    message=f"'{col.name}' is 100% missing.",
                ))
            elif col.missing_pct >= _SEVERE_MISSING_PCT:
                out.append(DoctorFinding(
                    check="Severe missingness",
                    category=CAT_COMPLETENESS,
                    severity=DoctorSeverity.CRITICAL,
                    columns=[col.name],
                    message=f"'{col.name}' is {col.missing_pct:.1%} missing.",
                ))
            elif col.missing_pct >= _HIGH_MISSING_PCT:
                out.append(DoctorFinding(
                    check="High missingness",
                    category=CAT_COMPLETENESS,
                    severity=DoctorSeverity.WARNING,
                    columns=[col.name],
                    message=f"'{col.name}' is {col.missing_pct:.1%} missing.",
                ))
        for col_a, col_b, p_both in missing_result.correlated_pairs:
            out.append(DoctorFinding(
                check="Correlated missingness",
                category=CAT_COMPLETENESS,
                severity=DoctorSeverity.INFO,
                columns=[col_a, col_b],
                message=f"'{col_a}' and '{col_b}' are missing together in {p_both:.1%} of rows.",
            ))
        return out

    # ------------------------------------------------------------------
    # Duplication
    # ------------------------------------------------------------------

    def _duplicate_column_pairs(self, df: pd.DataFrame) -> list[tuple[str, str]]:
        if df.shape[1] < 2 or len(df) == 0:
            return []
        by_hash: dict[int, list[str]] = {}
        for col in df.columns:
            try:
                h = int(pd.util.hash_pandas_object(df[col], index=False).sum())
            except TypeError:
                continue  # unhashable cell values (lists, dicts) — skip the column
            by_hash.setdefault(h, []).append(col)
        pairs: list[tuple[str, str]] = []
        for group in by_hash.values():
            for i, col_a in enumerate(group):
                for col_b in group[i + 1:]:
                    if df[col_a].equals(df[col_b]):
                        pairs.append((str(col_a), str(col_b)))
        return pairs

    def _duplication(
        self, df: pd.DataFrame, dup_col_pairs: list[tuple[str, str]]
    ) -> list[DoctorFinding]:
        out: list[DoctorFinding] = []
        n = len(df)
        if n > 0:
            dup_count = int(df.duplicated().sum())
            dup_pct = dup_count / n
            if dup_count > 0:
                if dup_pct >= _DUP_ROWS_CRITICAL_PCT:
                    severity = DoctorSeverity.CRITICAL
                elif dup_pct >= _DUP_ROWS_WARNING_PCT:
                    severity = DoctorSeverity.WARNING
                else:
                    severity = DoctorSeverity.INFO
                out.append(DoctorFinding(
                    check="Duplicate rows",
                    category=CAT_DUPLICATION,
                    severity=severity,
                    columns=[],
                    message=(
                        f"{dup_count:,} duplicate row{_plural(dup_count)} "
                        f"({dup_pct:.1%} of the dataset)."
                    ),
                ))
        for col_a, col_b in dup_col_pairs:
            out.append(DoctorFinding(
                check="Duplicate columns",
                category=CAT_DUPLICATION,
                severity=DoctorSeverity.CRITICAL,
                columns=[col_a, col_b],
                message=f"'{col_a}' and '{col_b}' contain identical values.",
            ))
        return out

    # ------------------------------------------------------------------
    # Type integrity
    # ------------------------------------------------------------------

    def _type_integrity(
        self, df: pd.DataFrame, quality_report: QualityReport | None
    ) -> list[DoctorFinding]:
        out: list[DoctorFinding] = []
        if quality_report is not None:
            for issue in quality_report.issues:
                if issue.check.startswith("Mixed types: "):
                    out.append(DoctorFinding(
                        check="Mixed types",
                        category=CAT_TYPE_INTEGRITY,
                        severity=DoctorSeverity.WARNING,
                        columns=[issue.check.removeprefix("Mixed types: ")],
                        message=issue.result,
                    ))
                elif issue.check == "All-object dtypes":
                    out.append(DoctorFinding(
                        check="All-text columns",
                        category=CAT_TYPE_INTEGRITY,
                        severity=DoctorSeverity.WARNING,
                        columns=[],
                        message=issue.result,
                    ))

        for col in df.select_dtypes(include="object").columns:
            clean = df[col].dropna()
            n = len(clean)
            if n == 0:
                continue
            as_str = clean.astype(str)

            numeric_share = float(pd.to_numeric(as_str, errors="coerce").notna().mean())
            if numeric_share >= _NUMERIC_AS_TEXT_SHARE:
                out.append(DoctorFinding(
                    check="Numeric stored as text",
                    category=CAT_TYPE_INTEGRITY,
                    severity=DoctorSeverity.WARNING,
                    columns=[str(col)],
                    message=(
                        f"'{col}' is stored as text but {numeric_share:.1%} of its values "
                        f"parse as numbers."
                    ),
                ))
            elif numeric_share < 0.5 and n >= 5 and self._parses_as_dates(as_str):
                out.append(DoctorFinding(
                    check="Dates stored as text",
                    category=CAT_TYPE_INTEGRITY,
                    severity=DoctorSeverity.INFO,
                    columns=[str(col)],
                    message=f"'{col}' is stored as text but its values parse as dates.",
                ))

            stripped = as_str.str.strip().str.lower()
            sentinel_mask = stripped.isin(_MISSING_SENTINELS)
            sentinel_count = int(sentinel_mask.sum())
            if sentinel_count > 0:
                examples = sorted(set(as_str[sentinel_mask].str.strip()))[:3]
                examples_str = ", ".join(f"'{e}'" for e in examples)
                out.append(DoctorFinding(
                    check="Disguised missing values",
                    category=CAT_TYPE_INTEGRITY,
                    severity=DoctorSeverity.WARNING,
                    columns=[str(col)],
                    message=(
                        f"'{col}' contains {sentinel_count:,} placeholder "
                        f"value{_plural(sentinel_count)} that read as missing ({examples_str})."
                    ),
                ))

            uniques = as_str.unique()
            if 1 < len(uniques) <= 200:
                groups: dict[str, list[str]] = {}
                for value in uniques:
                    groups.setdefault(value.strip().casefold(), []).append(value)
                variant_groups = [g for g in groups.values() if len(g) > 1]
                if variant_groups:
                    example = " / ".join(f"'{v}'" for v in variant_groups[0][:3])
                    out.append(DoctorFinding(
                        check="Inconsistent category labels",
                        category=CAT_TYPE_INTEGRITY,
                        severity=DoctorSeverity.WARNING,
                        columns=[str(col)],
                        message=(
                            f"'{col}' mixes case/whitespace variants of the same value "
                            f"({len(variant_groups)} value{_plural(len(variant_groups))} "
                            f"affected, e.g. {example})."
                        ),
                    ))
        return out

    @staticmethod
    def _parses_as_dates(as_str: pd.Series, sample_size: int = 500) -> bool:
        sample = as_str.head(sample_size)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
            except (TypeError, ValueError):
                parsed = pd.to_datetime(sample, errors="coerce")
        return bool(parsed.notna().mean() >= _DATE_AS_TEXT_SHARE)

    # ------------------------------------------------------------------
    # Feature quality
    # ------------------------------------------------------------------

    def _feature_quality(
        self,
        df: pd.DataFrame,
        dist_result: DistributionResult,
        outlier_result: OutlierResult | None,
    ) -> list[DoctorFinding]:
        out: list[DoctorFinding] = []

        all_stats: list[NumericColumnStats | CategoricalColumnStats] = [
            *dist_result.numeric, *dist_result.categorical,
        ]

        constant_cols: set[str] = set()
        for stats in all_stats:
            if stats.count > 0 and stats.unique_count == 1:
                constant_cols.add(stats.name)
                out.append(DoctorFinding(
                    check="Constant column",
                    category=CAT_FEATURE_QUALITY,
                    severity=DoctorSeverity.CRITICAL,
                    columns=[stats.name],
                    message=f"'{stats.name}' has only one unique value.",
                ))

        for col in df.columns:
            if str(col) in constant_cols:
                continue
            clean = df[col].dropna()
            n = len(clean)
            if n < 20:
                continue
            try:
                value_counts = clean.value_counts()
            except TypeError:
                continue
            if len(value_counts) <= 1:
                continue
            top_share = float(value_counts.iloc[0]) / n
            if top_share >= _NEAR_CONSTANT_SHARE:
                top_value = str(value_counts.index[0])[:30]
                out.append(DoctorFinding(
                    check="Near-constant column",
                    category=CAT_FEATURE_QUALITY,
                    severity=DoctorSeverity.WARNING,
                    columns=[str(col)],
                    message=(
                        f"'{col}' is near-constant — {top_share:.1%} of values "
                        f"are '{top_value}'."
                    ),
                ))

        id_cols: set[str] = set()
        for num_stats in dist_result.numeric:
            if num_stats.count >= 50 and num_stats.unique_pct > _ID_NUMERIC_UNIQUE_PCT:
                if num_stats.name not in df.columns:
                    continue
                values = df[num_stats.name].dropna()
                # High cardinality alone also fires for continuous measurements — only
                # call it an identifier when every value is whole-numbered.
                if not values.empty and bool((values % 1 == 0).all()):
                    id_cols.add(num_stats.name)
        for cat_stats in dist_result.categorical:
            if cat_stats.count >= 20 and cat_stats.unique_pct >= _ID_CATEGORICAL_UNIQUE_PCT:
                if cat_stats.name in df.columns and pd.api.types.is_datetime64_any_dtype(
                    df[cat_stats.name]
                ):
                    continue
                id_cols.add(cat_stats.name)
        for stats in all_stats:
            if stats.name in id_cols:
                out.append(DoctorFinding(
                    check="Identifier column",
                    category=CAT_FEATURE_QUALITY,
                    severity=DoctorSeverity.WARNING,
                    columns=[stats.name],
                    message=(
                        f"'{stats.name}' appears to be an identifier "
                        f"({stats.unique_count:,} unique values in {stats.count:,} rows)."
                    ),
                ))

        for cat_stats in dist_result.categorical:
            if cat_stats.name in id_cols or cat_stats.count == 0:
                continue
            if cat_stats.unique_count > _HIGH_CARDINALITY_UNIQUE:
                if cat_stats.name in df.columns and pd.api.types.is_datetime64_any_dtype(
                    df[cat_stats.name]
                ):
                    continue
                out.append(DoctorFinding(
                    check="High-cardinality column",
                    category=CAT_FEATURE_QUALITY,
                    severity=DoctorSeverity.INFO,
                    columns=[cat_stats.name],
                    message=f"'{cat_stats.name}' has {cat_stats.unique_count:,} unique categories.",
                ))

        if outlier_result is not None:
            for col_outliers in outlier_result.columns:
                if col_outliers.name in id_cols:
                    continue
                if col_outliers.iqr_extreme_pct >= _EXTREME_OUTLIER_PCT:
                    out.append(DoctorFinding(
                        check="Extreme outliers",
                        category=CAT_FEATURE_QUALITY,
                        severity=DoctorSeverity.WARNING,
                        columns=[col_outliers.name],
                        message=(
                            f"{col_outliers.iqr_extreme_pct:.1%} of values in "
                            f"'{col_outliers.name}' lie beyond the extreme outlier "
                            f"fence (3×IQR)."
                        ),
                    ))
        return out

    # ------------------------------------------------------------------
    # Redundancy
    # ------------------------------------------------------------------

    def _redundancy(
        self, corr_result: CorrelationResult | None, dup_col_pairs: list[tuple[str, str]]
    ) -> list[DoctorFinding]:
        out: list[DoctorFinding] = []
        if corr_result is None:
            return out
        dup_pairs = {frozenset(pair) for pair in dup_col_pairs}
        for col_a, col_b, r, _label in corr_result.strong_pairs:
            # Exact duplicates are already a CRITICAL Duplication finding.
            if abs(r) >= _NEAR_DUPLICATE_R and frozenset((col_a, col_b)) not in dup_pairs:
                out.append(DoctorFinding(
                    check="Near-duplicate features",
                    category=CAT_REDUNDANCY,
                    severity=DoctorSeverity.WARNING,
                    columns=[col_a, col_b],
                    message=f"'{col_a}' and '{col_b}' are nearly identical (r = {r:.3f}).",
                ))
        if corr_result.vif:
            for col, vif in sorted(corr_result.vif.items(), key=lambda item: -item[1]):
                if vif > _SEVERE_VIF:
                    out.append(DoctorFinding(
                        check="Severe multicollinearity",
                        category=CAT_REDUNDANCY,
                        severity=DoctorSeverity.WARNING,
                        columns=[col],
                        message=f"'{col}' has severe multicollinearity (VIF = {vif:.1f}).",
                    ))
        return out

    # ------------------------------------------------------------------
    # Target risks
    # ------------------------------------------------------------------

    def _target_risks(self, df: pd.DataFrame, target_result: TargetResult) -> list[DoctorFinding]:
        out: list[DoctorFinding] = []
        target_col = target_result.target_col
        if target_col not in df.columns:
            return out
        target = df[target_col]

        missing_pct = float(target.isna().mean())
        if missing_pct > 0:
            out.append(DoctorFinding(
                check="Missing target values",
                category=CAT_TARGET_RISKS,
                severity=DoctorSeverity.WARNING,
                columns=[target_col],
                message=f"Target '{target_col}' is {missing_pct:.1%} missing.",
            ))

        for feature in target_result.all_features:
            if feature.score >= _LEAKAGE_SCORE:
                out.append(DoctorFinding(
                    check="Possible target leakage",
                    category=CAT_TARGET_RISKS,
                    severity=DoctorSeverity.CRITICAL,
                    columns=[feature.feature],
                    message=(
                        f"'{feature.feature}' is almost perfectly associated with target "
                        f"'{target_col}' ({feature.method} = {feature.score:.3f})."
                    ),
                ))

        is_classification = (
            target_result.target_type == "categorical" or target.dropna().nunique() == 2
        )
        if is_classification:
            shares = target.value_counts(normalize=True)
            if len(shares) >= 2:
                minority_pct = float(shares.min())
                if minority_pct < _IMBALANCE_MINORITY_PCT:
                    minority_class = str(shares.idxmin())
                    out.append(DoctorFinding(
                        check="Class imbalance",
                        category=CAT_TARGET_RISKS,
                        severity=DoctorSeverity.WARNING,
                        columns=[target_col],
                        message=(
                            f"Smallest target class '{minority_class}' is only "
                            f"{minority_pct:.1%} of rows."
                        ),
                    ))
        return out
