from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from scipy import stats


@dataclass
class FeatureImportance:
    feature: str
    score: float       # |r| or Cramér's V
    method: str        # "pearson" | "point_biserial" | "cramers_v" | "eta_squared"
    direction: str     # "positive" | "negative" | "N/A"


@dataclass
class TargetResult:
    target_col: str
    target_type: str                        # "numeric" | "categorical"
    top_features: list[FeatureImportance]   # top 5 by |score|
    all_features: list[FeatureImportance]   # full list for appendix
    warnings: list[str] = field(default_factory=list)


class TargetAnalyzer:
    def analyze(self, df: pd.DataFrame, target_col: str) -> TargetResult:
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in dataset")

        target = df[target_col]
        target_type = "numeric" if pd.api.types.is_numeric_dtype(target) else "categorical"
        features: list[FeatureImportance] = []

        other_cols = [c for c in df.columns if c != target_col]

        if target_type == "numeric":
            features = self._numeric_target(df, target, other_cols)
        else:
            features = self._categorical_target(df, target, other_cols)

        features.sort(key=lambda f: -f.score)

        warnings = _check_target_assumptions(df=df, target=target, target_type=target_type)

        return TargetResult(
            target_col=target_col,
            target_type=target_type,
            top_features=features[:5],
            all_features=features,
            warnings=warnings,
        )

    def _numeric_target(
        self, df: pd.DataFrame, target: pd.Series, other_cols: list[str]
    ) -> list[FeatureImportance]:
        features = []
        for col in other_cols:
            series = df[col]
            if pd.api.types.is_numeric_dtype(series):
                combined = pd.concat([series, target], axis=1).dropna()
                if len(combined) < 5:
                    continue
                r, _ = stats.pearsonr(combined.iloc[:, 0], combined.iloc[:, 1])
                features.append(FeatureImportance(
                    feature=col,
                    score=abs(float(r)),
                    method="pearson",
                    direction="positive" if r > 0 else "negative",
                ))
            else:
                unique_vals = series.dropna().unique()
                if len(unique_vals) == 2:
                    binary = series.map({unique_vals[0]: 0, unique_vals[1]: 1})
                    combined = pd.concat([target, binary], axis=1).dropna()
                    if len(combined) < 5:
                        continue
                    r, _ = stats.pointbiserialr(combined.iloc[:, 0], combined.iloc[:, 1])
                    features.append(FeatureImportance(
                        feature=col,
                        score=abs(float(r)),
                        method="point_biserial",
                        direction="positive" if r > 0 else "negative",
                    ))
        return features

    def _categorical_target(
        self, df: pd.DataFrame, target: pd.Series, other_cols: list[str]
    ) -> list[FeatureImportance]:
        features = []
        for col in other_cols:
            series = df[col]
            if pd.api.types.is_numeric_dtype(series):
                unique_vals = target.dropna().unique()
                if len(unique_vals) == 2:
                    binary = target.map({unique_vals[0]: 0, unique_vals[1]: 1})
                    combined = pd.concat([series, binary], axis=1).dropna()
                    if len(combined) < 5:
                        continue
                    r, _ = stats.pointbiserialr(combined.iloc[:, 0], combined.iloc[:, 1])
                    features.append(FeatureImportance(
                        feature=col,
                        score=abs(float(r)),
                        method="point_biserial",
                        direction="positive" if r > 0 else "negative",
                    ))
                else:
                    groups = [
                        series[target == v].dropna().to_numpy()
                        for v in unique_vals
                        if len(series[target == v].dropna()) > 0
                    ]
                    if len(groups) < 2:
                        continue
                    try:
                        f, _ = stats.f_oneway(*groups)
                        k = len(groups)
                        n = sum(len(g) for g in groups)
                        eta2 = (f * (k - 1)) / (f * (k - 1) + (n - k)) if f > 0 else 0.0
                        features.append(FeatureImportance(
                            feature=col,
                            score=float(min(eta2, 1.0)),
                            method="eta_squared",
                            direction="N/A",
                        ))
                    except Exception:
                        continue
            else:
                v = self._cramers_v(series, target)
                if v > 0:
                    features.append(FeatureImportance(
                        feature=col,
                        score=v,
                        method="cramers_v",
                        direction="N/A",
                    ))
        return features

    def _cramers_v(self, s1: pd.Series, s2: pd.Series) -> float:
        try:
            import numpy as np
            ct = pd.crosstab(s1, s2)
            chi2 = stats.chi2_contingency(ct, correction=False)[0]
            n = ct.values.sum()
            k = min(ct.shape) - 1
            if n == 0 or k == 0:
                return 0.0
            return float(np.sqrt(chi2 / (n * k)))
        except Exception:
            return 0.0


def _check_target_assumptions(
    df: pd.DataFrame, target: pd.Series, target_type: str
) -> list[str]:
    notes: list[str] = []

    if target_type == "categorical":
        unique_vals = target.dropna().unique()
        n_classes = len(unique_vals)

        if n_classes > 2:
            # Check Levene's test for homogeneity of variances (ANOVA assumption)
            num_cols = df.select_dtypes(include="number").columns.tolist()
            levene_violations = []
            for col in num_cols:
                if col == target.name:
                    continue
                groups = [
                    df[col][target == v].dropna().to_numpy()
                    for v in unique_vals
                    if len(df[col][target == v].dropna()) >= 2
                ]
                if len(groups) < 2:
                    continue
                try:
                    _, lev_p = stats.levene(*groups)
                    if lev_p < 0.05:
                        levene_violations.append(col)
                except Exception:
                    continue

            if levene_violations:
                cols_str = ", ".join(levene_violations[:5])
                notes.append(
                    f"Levene's test rejects equal group variances (p < 0.05) for: {cols_str}. "
                    f"ANOVA / eta-squared assumes homogeneity of variances. "
                    f"For these columns, eta-squared scores may be inflated. "
                    f"Consider Welch's ANOVA or a non-parametric alternative (Kruskal-Wallis)."
                )

        # Small group sizes
        group_sizes = target.value_counts()
        small_groups = group_sizes[group_sizes < 30]
        if len(small_groups) > 0:
            groups_str = ", ".join(f"'{v}' (n={c})" for v, c in small_groups.items())
            notes.append(
                f"Small group size(s): {groups_str}. "
                f"Correlation estimates for these classes are unstable. "
                f"Point-biserial and eta-squared require n ≥ 30 per group for reliable inference."
            )

    else:
        # Numeric target — check if Pearson is appropriate (target skewness)
        arr = target.dropna().to_numpy(dtype=float)
        if len(arr) >= 3:
            target_skew = float(stats.skew(arr))
            if abs(target_skew) > 2.0:
                direction = "right" if target_skew > 0 else "left"
                notes.append(
                    f"Target column is heavily {direction}-skewed (skew = {target_skew:.2f}). "
                    f"Pearson correlation (used for numeric features) assumes bivariate normality. "
                    f"Scores may understate true associations. "
                    f"Consider log-transforming the target before modelling."
                )

    return notes
