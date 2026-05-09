from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class NumericColumnStats:
    name: str
    count: int
    null_count: int
    null_pct: float
    mean: float
    median: float
    mode: float | None
    std: float
    variance: float
    cv: float | None
    min: float
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float
    max: float
    iqr: float
    skewness: float
    excess_kurtosis: float
    unique_count: int
    unique_pct: float
    normality_test: str
    normality_pvalue: float | None
    assumptions: list[str] = field(default_factory=list)


@dataclass
class CategoricalColumnStats:
    name: str
    count: int
    null_count: int
    null_pct: float
    unique_count: int
    unique_pct: float
    mode: str | None
    mode_frequency: int
    entropy: float
    top_values: list[tuple[str, int, float]]  # (value, count, pct)
    assumptions: list[str] = field(default_factory=list)


@dataclass
class DistributionResult:
    numeric: list[NumericColumnStats]
    categorical: list[CategoricalColumnStats]


class DistributionAnalyzer:
    def analyze(self, df: pd.DataFrame) -> DistributionResult:
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        categorical_cols = df.select_dtypes(exclude="number").columns.tolist()

        numeric_stats = [self._numeric_stats(df[col]) for col in numeric_cols]
        categorical_stats = [self._categorical_stats(df[col]) for col in categorical_cols]

        return DistributionResult(numeric=numeric_stats, categorical=categorical_stats)

    def _numeric_stats(self, s: pd.Series) -> NumericColumnStats:
        clean = s.dropna()
        n = len(clean)
        null_count = int(s.isna().sum())
        null_pct = null_count / len(s) if len(s) > 0 else 0.0

        if n == 0:
            return NumericColumnStats(
                name=str(s.name), count=0, null_count=null_count, null_pct=null_pct,
                mean=float("nan"), median=float("nan"), mode=None, std=float("nan"),
                variance=float("nan"), cv=None, min=float("nan"), p5=float("nan"),
                p25=float("nan"), p50=float("nan"), p75=float("nan"), p95=float("nan"),
                max=float("nan"), iqr=float("nan"), skewness=float("nan"),
                excess_kurtosis=float("nan"), unique_count=0, unique_pct=0.0,
                normality_test="N/A", normality_pvalue=None,
            )

        arr = clean.to_numpy(dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        cv = (std / abs(mean)) if mean != 0 else None

        mode_result = clean.mode()
        mode_val = float(mode_result.iloc[0]) if len(mode_result) > 0 else None

        percentiles = np.percentile(arr, [5, 25, 50, 75, 95])
        iqr = float(percentiles[3] - percentiles[1])

        skewness = float(stats.skew(arr)) if n >= 3 else float("nan")
        excess_kurtosis = float(stats.kurtosis(arr)) if n >= 4 else float("nan")

        # Normality test
        normality_label = "N/A"
        normality_pvalue = None
        if n >= 8:
            if n <= 5000:
                _, pval = stats.shapiro(arr)
                normality_label = "Shapiro-Wilk"
            else:
                _, pval = stats.normaltest(arr)
                normality_label = "D'Agostino-Pearson"
            normality_pvalue = float(pval)

        unique_count = int(clean.nunique())

        assumptions = _check_distribution_assumptions(
            n=n, mean=mean, median=float(np.median(arr)), std=std,
            skewness=skewness, excess_kurtosis=excess_kurtosis,
            normality_label=normality_label, normality_pvalue=normality_pvalue,
            unique_count=unique_count,
        )

        return NumericColumnStats(
            name=str(s.name),
            count=n,
            null_count=null_count,
            null_pct=null_pct,
            mean=mean,
            median=float(np.median(arr)),
            mode=mode_val,
            std=std,
            variance=float(std ** 2),
            cv=cv,
            min=float(arr.min()),
            p5=float(percentiles[0]),
            p25=float(percentiles[1]),
            p50=float(percentiles[2]),
            p75=float(percentiles[3]),
            p95=float(percentiles[4]),
            max=float(arr.max()),
            iqr=iqr,
            skewness=skewness,
            excess_kurtosis=excess_kurtosis,
            unique_count=unique_count,
            unique_pct=unique_count / n,
            normality_test=normality_label,
            normality_pvalue=normality_pvalue,
            assumptions=assumptions,
        )

    def _categorical_stats(self, s: pd.Series) -> CategoricalColumnStats:
        clean = s.dropna().astype(str)
        n = len(clean)
        null_count = int(s.isna().sum())
        null_pct = null_count / len(s) if len(s) > 0 else 0.0

        value_counts = clean.value_counts()
        unique_count = int(value_counts.shape[0])

        if n == 0:
            return CategoricalColumnStats(
                name=str(s.name), count=0, null_count=null_count, null_pct=null_pct,
                unique_count=0, unique_pct=0.0, mode=None, mode_frequency=0,
                entropy=0.0, top_values=[],
            )

        mode_val = str(value_counts.index[0]) if unique_count > 0 else None
        mode_freq = int(value_counts.iloc[0]) if unique_count > 0 else 0

        # Shannon entropy (normalized 0-1) — probs > 0 guaranteed by value_counts
        probs = (value_counts / n).to_numpy(dtype=float)
        raw_entropy = float(-np.sum(probs * np.log2(probs)))
        max_entropy = np.log2(unique_count) if unique_count > 1 else 1.0
        entropy = raw_entropy / max_entropy if max_entropy > 0 else 0.0

        top_values = [
            (str(val), int(cnt), float(cnt / n))
            for val, cnt in value_counts.head(10).items()
        ]

        assumptions = _check_categorical_assumptions(n=n, unique_count=unique_count)

        return CategoricalColumnStats(
            name=str(s.name),
            count=n,
            null_count=null_count,
            null_pct=null_pct,
            unique_count=unique_count,
            unique_pct=unique_count / n,
            mode=mode_val,
            mode_frequency=mode_freq,
            entropy=entropy,
            top_values=top_values,
            assumptions=assumptions,
        )


def _check_distribution_assumptions(
    n: int,
    mean: float,
    median: float,
    std: float,
    skewness: float,
    excess_kurtosis: float,
    normality_label: str,
    normality_pvalue: float | None,
    unique_count: int,
) -> list[str]:
    import math
    notes: list[str] = []

    if std == 0.0 and n > 1:
        notes.append(
            "Zero variance: all non-null values are identical. "
            "Descriptive statistics are trivial and correlations are undefined."
        )
        return notes  # nothing else meaningful to check

    if not math.isnan(skewness):
        if abs(skewness) > 2.0:
            direction = "right" if skewness > 0 else "left"
            notes.append(
                f"Heavily {direction}-skewed (skew = {skewness:.2f}): "
                f"mean ({mean:.4g}) is substantially pulled toward the tail. "
                f"Median ({median:.4g}) and IQR are more robust descriptors for this column."
            )
        elif abs(skewness) > 1.0:
            direction = "right" if skewness > 0 else "left"
            notes.append(
                f"Moderately {direction}-skewed (skew = {skewness:.2f}): "
                f"mean ({mean:.4g}) may overstate the typical value. "
                f"Consider reporting median ({median:.4g}) alongside mean."
            )

    if normality_pvalue is not None and normality_pvalue < 0.05:
        if n > 2000:
            notes.append(
                f"Large sample (n = {n:,}): {normality_label} has very high statistical power — "
                f"even trivially small deviations from normality produce p < 0.05. "
                f"Use skewness ({skewness:.2f}) and excess kurtosis ({excess_kurtosis:.2f}) "
                f"to judge practical normality, not the p-value alone."
            )

    if mean < 0 and not math.isnan(skewness):
        notes.append(
            f"Negative mean ({mean:.4g}): CV is computed as std / |mean|. "
            f"CV is most interpretable for ratio-scale variables (strictly positive)."
        )

    if unique_count == 1:
        notes.append(
            "Only one unique value — this column carries no information and "
            "should likely be dropped before modelling."
        )
    elif n >= 50 and unique_count / n > 0.95:
        notes.append(
            f"Very high cardinality ({unique_count} unique values in {n} rows): "
            f"this may be an ID or free-text column rather than a true numeric feature."
        )

    return notes


def _check_categorical_assumptions(n: int, unique_count: int) -> list[str]:
    notes: list[str] = []
    if unique_count == 1:
        notes.append(
            "Only one unique category — this column carries no information "
            "and chi-squared / Cramér's V are undefined."
        )
    elif unique_count > 50:
        notes.append(
            f"High cardinality ({unique_count} unique values): chi-squared tests and "
            f"Cramér's V lose statistical power. Frequency-based analysis may be more meaningful."
        )
    if n < 30:
        notes.append(
            f"Small sample (n = {n}): frequency estimates are unreliable. "
            f"Interpret entropy and mode frequency with caution."
        )
    return notes
