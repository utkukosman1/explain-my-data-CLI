from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

STRONG_CORRELATION_THRESHOLD = 0.7


@dataclass
class CorrelationResult:
    pearson: pd.DataFrame | None
    spearman: pd.DataFrame | None
    strong_pairs: list[tuple[str, str, float, str]]  # col_a, col_b, r, label
    cramers_v: pd.DataFrame | None                   # categorical vs categorical
    point_biserial: list[tuple[str, str, float, float]]  # num_col, bin_col, r, p
    vif: dict[str, float] | None
    warnings: list[str] = field(default_factory=list)


class CorrelationAnalyzer:
    def analyze(self, df: pd.DataFrame) -> CorrelationResult:
        num_df = df.select_dtypes(include="number")
        cat_df = df.select_dtypes(exclude="number")

        pearson = spearman = None
        if num_df.shape[1] >= 2:
            pearson = num_df.corr(method="pearson")
            spearman = num_df.corr(method="spearman")

        strong_pairs = self._strong_pairs(pearson)
        cramers = self._cramers_matrix(cat_df) if cat_df.shape[1] >= 2 else None
        pb = self._point_biserial(num_df, cat_df)
        vif = self._vif(num_df)

        warnings = _check_correlation_assumptions(
            num_df=num_df,
            cat_df=cat_df,
            pearson=pearson,
            spearman=spearman,
            vif=vif,
        )

        return CorrelationResult(
            pearson=pearson,
            spearman=spearman,
            strong_pairs=strong_pairs,
            cramers_v=cramers,
            point_biserial=pb,
            vif=vif,
            warnings=warnings,
        )

    def _strong_pairs(
        self,
        corr: pd.DataFrame | None,
        threshold: float = STRONG_CORRELATION_THRESHOLD,
    ) -> list[tuple[str, str, float, str]]:
        if corr is None:
            return []
        pairs = []
        cols = corr.columns.tolist()
        for i, col_a in enumerate(cols):
            for col_b in cols[i + 1:]:
                r = corr.loc[col_a, col_b]
                if abs(r) >= threshold:
                    label = "strong positive" if r > 0 else "strong negative"
                    pairs.append((col_a, col_b, float(r), label))
        return sorted(pairs, key=lambda x: -abs(x[2]))

    def _cramers_matrix(self, cat_df: pd.DataFrame) -> pd.DataFrame:
        cols = cat_df.columns.tolist()
        n = len(cols)
        matrix = pd.DataFrame(np.zeros((n, n)), index=cols, columns=cols)
        for i, col_a in enumerate(cols):
            for j, col_b in enumerate(cols):
                if i == j:
                    matrix.loc[col_a, col_b] = 1.0
                elif i < j:
                    v = self._cramers_v(cat_df[col_a], cat_df[col_b])
                    matrix.loc[col_a, col_b] = v
                    matrix.loc[col_b, col_a] = v
        return matrix

    def _cramers_v(self, s1: pd.Series, s2: pd.Series) -> float:
        try:
            ct = pd.crosstab(s1, s2)
            chi2 = stats.chi2_contingency(ct, correction=False)[0]
            n = ct.values.sum()
            k = min(ct.shape) - 1
            if n == 0 or k == 0:
                return 0.0
            return float(np.sqrt(chi2 / (n * k)))
        except Exception:
            return 0.0

    def _point_biserial(
        self, num_df: pd.DataFrame, cat_df: pd.DataFrame
    ) -> list[tuple[str, str, float, float]]:
        result = []
        for cat_col in cat_df.columns:
            unique_vals = cat_df[cat_col].dropna().unique()
            if len(unique_vals) != 2:
                continue
            binary = cat_df[cat_col].map({unique_vals[0]: 0, unique_vals[1]: 1})
            for num_col in num_df.columns:
                combined = pd.concat([num_df[num_col], binary], axis=1).dropna()
                if len(combined) < 5:
                    continue
                r, p = stats.pointbiserialr(combined.iloc[:, 0], combined.iloc[:, 1])
                result.append((str(num_col), str(cat_col), float(r), float(p)))
        return sorted(result, key=lambda x: -abs(x[2]))

    def _vif(self, num_df: pd.DataFrame) -> dict[str, float] | None:
        if num_df.shape[1] < 2:
            return None
        try:
            from statsmodels.stats.outliers_influence import variance_inflation_factor

            clean = num_df.dropna()
            if len(clean) < num_df.shape[1] * 10:
                return None
            # Intercept column required for correct VIF (avoids uncentered R²)
            X = np.column_stack([np.ones(len(clean)), clean.to_numpy(dtype=float)])
            return {
                col: float(variance_inflation_factor(X, i + 1))
                for i, col in enumerate(clean.columns)
            }
        except Exception:
            return None


def _check_correlation_assumptions(
    num_df: pd.DataFrame,
    cat_df: pd.DataFrame,
    pearson: pd.DataFrame | None,
    spearman: pd.DataFrame | None,
    vif: dict[str, float] | None,
) -> list[str]:
    notes: list[str] = []

    # Pearson vs Spearman discrepancy — signals non-linearity or outlier influence
    if pearson is not None and spearman is not None:
        cols = pearson.columns.tolist()
        for i, col_a in enumerate(cols):
            for col_b in cols[i + 1:]:
                p_r = float(pearson.loc[col_a, col_b])
                s_r = float(spearman.loc[col_a, col_b])
                diff = abs(p_r - s_r)
                if diff > 0.15 and abs(s_r) > 0.2:
                    notes.append(
                        f"{col_a} × {col_b}: Pearson r = {p_r:.2f} vs Spearman ρ = {s_r:.2f} "
                        f"(gap = {diff:.2f}). A large gap indicates a non-linear relationship "
                        f"or strong outlier influence on Pearson. "
                        f"Spearman is the more reliable measure for non-normal data."
                    )

    # High VIF — multicollinearity warning
    if vif:
        for col, v in vif.items():
            if v > 10:
                notes.append(
                    f"VIF({col}) = {v:.1f} > 10: severe multicollinearity detected. "
                    f"OLS coefficient estimates for this variable will be unstable. "
                    f"Consider removing, combining, or regularising collinear features before modelling."
                )
            elif v > 5:
                notes.append(
                    f"VIF({col}) = {v:.1f} > 5: moderate multicollinearity. "
                    f"Monitor this variable if using linear regression."
                )

    # High-cardinality Cramér's V — chi-squared loses power
    for col in cat_df.columns:
        u = cat_df[col].nunique()
        if u > 20:
            notes.append(
                f"'{col}' has {u} unique categories: chi-squared (and therefore Cramér's V) "
                f"loses statistical power with high-cardinality variables. "
                f"Interpret Cramér's V values with caution — consider grouping rare categories first."
            )

    # Pearson on heavily skewed numeric columns
    if num_df.shape[1] >= 2:
        skewed_cols = []
        for col in num_df.columns:
            arr = num_df[col].dropna().to_numpy(dtype=float)
            if len(arr) >= 3:
                sk = float(stats.skew(arr))
                if abs(sk) > 2.0:
                    skewed_cols.append((col, sk))
        if len(skewed_cols) >= 2:
            names = ", ".join(f"{c} (skew={s:.2f})" for c, s in skewed_cols[:3])
            notes.append(
                f"Multiple heavily skewed columns ({names}): Pearson correlation assumes "
                f"linearity and is sensitive to outliers in skewed distributions. "
                f"Spearman correlation is more appropriate — refer to the Spearman heatmap."
            )

    return notes
