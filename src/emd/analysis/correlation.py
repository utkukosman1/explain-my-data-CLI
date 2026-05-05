from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class CorrelationResult:
    pearson: pd.DataFrame | None
    spearman: pd.DataFrame | None
    strong_pairs: list[tuple[str, str, float, str]]  # col_a, col_b, r, label
    cramers_v: pd.DataFrame | None                   # categorical vs categorical
    point_biserial: list[tuple[str, str, float, float]]  # num_col, bin_col, r, p
    vif: dict[str, float] | None


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

        return CorrelationResult(
            pearson=pearson,
            spearman=spearman,
            strong_pairs=strong_pairs,
            cramers_v=cramers,
            point_biserial=pb,
            vif=vif,
        )

    def _strong_pairs(
        self,
        corr: pd.DataFrame | None,
        threshold: float = 0.7,
    ) -> list[tuple[str, str, float, str]]:
        if corr is None:
            return []
        pairs = []
        cols = corr.columns.tolist()
        for i, col_a in enumerate(cols):
            for col_b in cols[i + 1 :]:
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
            X = clean.to_numpy(dtype=float)
            return {
                col: float(variance_inflation_factor(X, i))
                for i, col in enumerate(clean.columns)
            }
        except Exception:
            return None
