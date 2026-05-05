from __future__ import annotations

from dataclasses import dataclass

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
        cv = (std / mean) if mean != 0 else None

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
                stat, pval = stats.shapiro(arr[:5000])
                normality_label = "Shapiro-Wilk"
            else:
                stat, pval = stats.normaltest(arr)
                normality_label = "D'Agostino-Pearson"
            normality_pvalue = float(pval)

        unique_count = int(clean.nunique())

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

        # Shannon entropy (normalized 0-1)
        probs = value_counts / n
        raw_entropy = float(-np.sum(probs * np.log2(probs + 1e-12)))
        max_entropy = np.log2(unique_count) if unique_count > 1 else 1.0
        entropy = raw_entropy / max_entropy if max_entropy > 0 else 0.0

        top_values = [
            (str(val), int(cnt), float(cnt / n))
            for val, cnt in value_counts.head(10).items()
        ]

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
        )
