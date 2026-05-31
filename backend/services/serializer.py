from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np
import pandas as pd


def safe(obj: Any) -> Any:
    """Recursively make a value JSON-serializable."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, pd.DataFrame):
        return {
            str(col): {str(idx): safe(val) for idx, val in col_data.items()}
            for col, col_data in obj.to_dict().items()
        }
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: safe(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [safe(i) for i in obj]
    if isinstance(obj, dict):
        return {str(k): safe(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [safe(i) for i in obj]
    return obj


def numeric_histogram(series: pd.Series, bins: int = 30) -> list[dict[str, Any]]:
    """Returns recharts-ready histogram bins."""
    clean = series.dropna()
    if len(clean) == 0:
        return []
    n_bins = min(bins, max(1, clean.nunique()))
    counts, edges = np.histogram(clean.to_numpy(dtype=float), bins=n_bins)
    return [
        {
            "bin": f"{edges[i]:.4g}–{edges[i+1]:.4g}",
            "x": safe(float(edges[i])),
            "x1": safe(float(edges[i + 1])),
            "count": int(counts[i]),
        }
        for i in range(len(counts))
    ]


def categorical_bars(top_values: list[tuple[str, int, float]]) -> list[dict[str, Any]]:
    """Returns recharts-ready bar chart data from CategoricalColumnStats.top_values."""
    return [
        {"value": str(v), "count": int(c), "pct": round(float(p) * 100, 2)}
        for v, c, p in top_values
    ]


def corr_heatmap(df: pd.DataFrame | None) -> list[dict[str, Any]] | None:
    """Flat list of {row, col, value} for recharts heatmap."""
    if df is None:
        return None
    return [
        {"row": str(col_a), "col": str(col_b), "value": safe(df.loc[col_a, col_b])}
        for col_a in df.index
        for col_b in df.columns
    ]


def missing_bars(missing_result: Any) -> list[dict[str, Any]]:
    """Per-column missing % bar data for recharts."""
    return [
        {"column": c.name, "missing_pct": round(c.missing_pct * 100, 2), "missing_count": c.missing_count}
        for c in missing_result.columns
        if c.missing_count > 0
    ]


def outlier_bars(outlier_result: Any) -> list[dict[str, Any]]:
    """Per-column outlier counts by method for recharts grouped bar chart."""
    return [
        {
            "column": c.name,
            "IQR": c.iqr_count,
            "IQR_extreme": c.iqr_extreme_count,
            "Z_score": c.zscore_count,
            "Modified_Z": c.mzscore_count,
        }
        for c in outlier_result.columns
    ]


def drift_overlay(col_name: str, ref_series: pd.Series, cur_series: pd.Series, bins: int = 25) -> list[dict[str, Any]]:
    """Overlay histogram for drift chart. Returns [{bin, ref_count, cur_count}, ...]."""
    ref_clean = ref_series.dropna().to_numpy(dtype=float)
    cur_clean = cur_series.dropna().to_numpy(dtype=float)
    if len(ref_clean) == 0 and len(cur_clean) == 0:
        return []
    all_vals = np.concatenate([ref_clean, cur_clean])
    _, edges = np.histogram(all_vals, bins=bins)
    ref_counts, _ = np.histogram(ref_clean, bins=edges)
    cur_counts, _ = np.histogram(cur_clean, bins=edges)
    return [
        {
            "bin": f"{edges[i]:.4g}–{edges[i+1]:.4g}",
            "x": safe(float(edges[i])),
            "reference": int(ref_counts[i]),
            "current": int(cur_counts[i]),
        }
        for i in range(len(ref_counts))
    ]
