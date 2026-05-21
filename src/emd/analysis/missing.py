from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ColumnMissing:
    name: str
    missing_count: int
    missing_pct: float
    present_count: int


@dataclass
class MissingPattern:
    pattern: dict[str, bool]  # col -> is_missing
    row_count: int
    row_pct: float


@dataclass
class MissingResult:
    columns: list[ColumnMissing]
    total_cells: int
    total_missing: int
    global_missing_pct: float
    complete_rows: int
    complete_rows_pct: float
    patterns: list[MissingPattern]
    correlated_pairs: list[tuple[str, str, float]]  # (col_a, col_b, P(both missing))


class MissingAnalyzer:
    def analyze(self, df: pd.DataFrame) -> MissingResult:
        n_rows, n_cols = df.shape
        total_cells = n_rows * n_cols

        columns = []
        for col in df.columns:
            mc = int(df[col].isna().sum())
            columns.append(ColumnMissing(
                name=str(col),
                missing_count=mc,
                missing_pct=mc / n_rows if n_rows > 0 else 0.0,
                present_count=n_rows - mc,
            ))

        total_missing = int(df.isna().sum().sum())
        complete_rows = int(df.dropna().shape[0])
        patterns = self._compute_patterns(df)
        correlated_pairs = self._correlated_missingness(df)

        return MissingResult(
            columns=columns,
            total_cells=total_cells,
            total_missing=total_missing,
            global_missing_pct=total_missing / total_cells if total_cells > 0 else 0.0,
            complete_rows=complete_rows,
            complete_rows_pct=complete_rows / n_rows if n_rows > 0 else 0.0,
            patterns=patterns,
            correlated_pairs=correlated_pairs,
        )

    def _compute_patterns(self, df: pd.DataFrame, max_patterns: int = 10) -> list[MissingPattern]:
        missing_cols = [c for c in df.columns if df[c].isna().any()]
        if not missing_cols:
            return []

        mask = df[missing_cols].isna()
        pattern_counts: dict[tuple[bool, ...], int] = Counter(
            map(tuple, mask.to_numpy())
        )

        n = len(df)
        patterns = []
        for key, count in sorted(pattern_counts.items(), key=lambda x: -x[1])[:max_patterns]:
            if any(key):  # skip fully-present rows
                patterns.append(MissingPattern(
                    pattern=dict(zip(missing_cols, key)),
                    row_count=count,
                    row_pct=count / n,
                ))
        return patterns

    def _correlated_missingness(
        self, df: pd.DataFrame, threshold: float = 0.5
    ) -> list[tuple[str, str, float]]:
        missing_cols = [c for c in df.columns if df[c].isna().any()]
        if len(missing_cols) < 2:
            return []

        result = []
        mask = df[missing_cols].isna()
        n = len(df)
        for i, col_a in enumerate(missing_cols):
            for col_b in missing_cols[i + 1 :]:
                both = int((mask[col_a] & mask[col_b]).sum())
                either = int((mask[col_a] | mask[col_b]).sum())
                p_both = both / n
                if either > 0 and p_both >= threshold:
                    result.append((col_a, col_b, p_both))
        return sorted(result, key=lambda x: -x[2])
