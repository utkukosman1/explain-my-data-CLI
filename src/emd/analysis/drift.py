from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class ColumnDrift:
    name: str
    col_type: str               # "numeric" | "categorical"
    # Numeric fields
    mean_a: float | None = None
    mean_b: float | None = None
    mean_shift_pct: float | None = None
    std_a: float | None = None
    std_b: float | None = None
    ks_statistic: float | None = None
    ks_pvalue: float | None = None
    psi: float | None = None
    # Categorical fields
    chi2_statistic: float | None = None
    chi2_pvalue: float | None = None
    # Verdict
    drift_detected: bool = False
    drift_severity: str = "none"    # "none" | "moderate" | "high"


@dataclass
class DriftResult:
    columns: list[ColumnDrift]
    drifted_columns: list[str]
    drift_fraction: float
    overall_drift: bool
    reference_shape: tuple[int, int]
    current_shape: tuple[int, int]
    missing_in_current: list[str]   # in reference but not current
    new_in_current: list[str]       # in current but not reference
    psi_threshold: float = 0.2


class DriftAnalyzer:
    def __init__(self, psi_threshold: float = 0.2) -> None:
        self.psi_threshold = psi_threshold

    def analyze(self, df_ref: pd.DataFrame, df_cur: pd.DataFrame) -> DriftResult:
        ref_cols = set(df_ref.columns)
        cur_cols = set(df_cur.columns)
        shared_cols = sorted(ref_cols & cur_cols)
        missing_in_current = sorted(ref_cols - cur_cols)
        new_in_current = sorted(cur_cols - ref_cols)

        column_results: list[ColumnDrift] = []
        for col in shared_cols:
            if pd.api.types.is_numeric_dtype(df_ref[col]):
                cd = self._numeric_drift(col, df_ref[col], df_cur[col])
            else:
                cd = self._categorical_drift(col, df_ref[col], df_cur[col])
            column_results.append(cd)

        drifted = [c.name for c in column_results if c.drift_detected]
        drift_fraction = len(drifted) / len(column_results) if column_results else 0.0

        return DriftResult(
            columns=column_results,
            drifted_columns=drifted,
            drift_fraction=drift_fraction,
            overall_drift=drift_fraction > 0.0 and len(drifted) > 0,
            reference_shape=df_ref.shape,
            current_shape=df_cur.shape,
            missing_in_current=missing_in_current,
            new_in_current=new_in_current,
            psi_threshold=self.psi_threshold,
        )

    def _numeric_drift(self, name: str, ref: pd.Series, cur: pd.Series) -> ColumnDrift:
        ref_clean = ref.dropna().to_numpy(dtype=float)
        cur_clean = cur.dropna().to_numpy(dtype=float)

        if len(ref_clean) < 5 or len(cur_clean) < 5:
            return ColumnDrift(name=name, col_type="numeric", drift_severity="none")

        mean_a = float(np.mean(ref_clean))
        mean_b = float(np.mean(cur_clean))
        std_a = float(np.std(ref_clean, ddof=1))
        std_b = float(np.std(cur_clean, ddof=1))
        mean_shift_pct = abs(mean_a - mean_b) / abs(mean_a) * 100 if mean_a != 0 else None

        ks_stat, ks_pval = stats.ks_2samp(ref_clean, cur_clean)
        psi = self._compute_psi(ref_clean, cur_clean)

        severity = self._psi_severity(psi)
        drift_detected = severity in ("moderate", "high")

        return ColumnDrift(
            name=name,
            col_type="numeric",
            mean_a=mean_a,
            mean_b=mean_b,
            mean_shift_pct=mean_shift_pct,
            std_a=std_a,
            std_b=std_b,
            ks_statistic=float(ks_stat),
            ks_pvalue=float(ks_pval),
            psi=psi,
            drift_detected=drift_detected,
            drift_severity=severity,
        )

    def _categorical_drift(self, name: str, ref: pd.Series, cur: pd.Series) -> ColumnDrift:
        ref_clean = ref.dropna().astype(str)
        cur_clean = cur.dropna().astype(str)

        if len(ref_clean) < 5 or len(cur_clean) < 5:
            return ColumnDrift(name=name, col_type="categorical", drift_severity="none")

        all_cats = sorted(set(ref_clean.unique()) | set(cur_clean.unique()))
        ref_counts = ref_clean.value_counts().reindex(all_cats, fill_value=0)
        cur_counts = cur_clean.value_counts().reindex(all_cats, fill_value=0)

        # Add small constant to avoid zero division in chi-squared
        ref_counts = ref_counts + 1e-6
        cur_counts = cur_counts + 1e-6

        try:
            chi2, pval, _, _ = stats.chi2_contingency(
                np.array([ref_counts.values, cur_counts.values])
            )
            drift_detected = float(pval) < 0.05
            severity = "high" if drift_detected else "none"
        except Exception:
            chi2, pval, drift_detected, severity = 0.0, 1.0, False, "none"

        return ColumnDrift(
            name=name,
            col_type="categorical",
            chi2_statistic=float(chi2),
            chi2_pvalue=float(pval),
            drift_detected=drift_detected,
            drift_severity=severity,
        )

    def _compute_psi(self, ref: np.ndarray, cur: np.ndarray, n_bins: int = 10) -> float:
        # Bin edges from reference quantiles (equal-frequency binning)
        quantiles = np.linspace(0, 100, n_bins + 1)
        bin_edges = np.percentile(ref, quantiles)
        # Ensure unique edges
        bin_edges = np.unique(bin_edges)
        if len(bin_edges) < 2:
            return 0.0

        ref_counts, _ = np.histogram(ref, bins=bin_edges)
        cur_counts, _ = np.histogram(cur, bins=bin_edges)

        ref_total = ref_counts.sum()
        cur_total = cur_counts.sum()
        if ref_total == 0 or cur_total == 0:
            return 0.0
        ref_pct = ref_counts / ref_total
        cur_pct = cur_counts / cur_total

        # Clip to avoid log(0)
        ref_pct = np.clip(ref_pct, 1e-6, None)
        cur_pct = np.clip(cur_pct, 1e-6, None)

        psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
        return max(0.0, psi)

    def _psi_severity(self, psi: float) -> str:
        if psi < 0.1:
            return "none"
        if psi < self.psi_threshold:
            return "moderate"
        return "high"
