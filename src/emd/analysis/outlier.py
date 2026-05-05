from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class ColumnOutliers:
    name: str
    iqr_count: int
    iqr_pct: float
    iqr_extreme_count: int
    iqr_extreme_pct: float
    zscore_count: int
    zscore_pct: float
    mzscore_count: int
    mzscore_pct: float
    iforest_count: int | None
    iforest_pct: float | None
    sample_outlier_indices: list[int] = field(default_factory=list)


@dataclass
class OutlierResult:
    columns: list[ColumnOutliers]
    methods_used: list[str]


class OutlierAnalyzer:
    def __init__(
        self,
        iqr_multiplier: float = 1.5,
        iqr_extreme_multiplier: float = 3.0,
        zscore_threshold: float = 3.0,
        mzscore_threshold: float = 3.5,
        use_iforest: bool = False,
        contamination: str = "auto",
    ) -> None:
        self.iqr_multiplier = iqr_multiplier
        self.iqr_extreme_multiplier = iqr_extreme_multiplier
        self.zscore_threshold = zscore_threshold
        self.mzscore_threshold = mzscore_threshold
        self.use_iforest = use_iforest
        self.contamination = contamination

    def analyze(self, df: pd.DataFrame) -> OutlierResult:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        methods = ["iqr", "zscore", "mzscore"]
        if self.use_iforest:
            methods.append("iforest")

        results = [self._column_outliers(df[col]) for col in num_cols]
        return OutlierResult(columns=results, methods_used=methods)

    def _column_outliers(self, s: pd.Series) -> ColumnOutliers:
        clean = s.dropna()
        n = len(clean)

        if n < 4:
            return ColumnOutliers(
                name=str(s.name), iqr_count=0, iqr_pct=0.0,
                iqr_extreme_count=0, iqr_extreme_pct=0.0,
                zscore_count=0, zscore_pct=0.0,
                mzscore_count=0, mzscore_pct=0.0,
                iforest_count=None, iforest_pct=None,
            )

        arr = clean.to_numpy(dtype=float)

        # IQR method
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        iqr_mask = (arr < q1 - self.iqr_multiplier * iqr) | (arr > q3 + self.iqr_multiplier * iqr)
        iqr_extreme_mask = (arr < q1 - self.iqr_extreme_multiplier * iqr) | (arr > q3 + self.iqr_extreme_multiplier * iqr)

        # Z-score method
        if arr.std(ddof=1) > 0:
            z_scores = np.abs(stats.zscore(arr, ddof=1))
            zscore_mask = z_scores > self.zscore_threshold
        else:
            zscore_mask = np.zeros(n, dtype=bool)

        # Modified Z-score (Iglewicz-Hoaglin)
        median = np.median(arr)
        mad = np.median(np.abs(arr - median))
        if mad > 0:
            mz = np.abs(0.6745 * (arr - median) / mad)
            mzscore_mask = mz > self.mzscore_threshold
        else:
            mzscore_mask = np.zeros(n, dtype=bool)

        # Isolation Forest (optional)
        iforest_count = iforest_pct = None
        if self.use_iforest:
            try:
                from sklearn.ensemble import IsolationForest
                clf = IsolationForest(contamination=self.contamination, random_state=42)
                preds = clf.fit_predict(arr.reshape(-1, 1))
                iforest_mask = preds == -1
                iforest_count = int(iforest_mask.sum())
                iforest_pct = iforest_count / n
            except ImportError:
                pass

        # Sample indices from original series for the report
        outlier_indices = list(clean.index[iqr_mask][:20])

        return ColumnOutliers(
            name=str(s.name),
            iqr_count=int(iqr_mask.sum()),
            iqr_pct=float(iqr_mask.sum() / n),
            iqr_extreme_count=int(iqr_extreme_mask.sum()),
            iqr_extreme_pct=float(iqr_extreme_mask.sum() / n),
            zscore_count=int(zscore_mask.sum()),
            zscore_pct=float(zscore_mask.sum() / n),
            mzscore_count=int(mzscore_mask.sum()),
            mzscore_pct=float(mzscore_mask.sum() / n),
            iforest_count=iforest_count,
            iforest_pct=iforest_pct,
            sample_outlier_indices=outlier_indices,
        )
