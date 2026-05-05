from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from emd.analysis.correlation import CorrelationResult
from emd.analysis.distribution import DistributionResult
from emd.analysis.missing import MissingResult
from emd.analysis.outlier import OutlierResult

matplotlib.use("Agg")  # non-interactive backend

LIGHT_STYLE = "seaborn-v0_8-whitegrid"
DARK_STYLE = "dark_background"


class ChartRenderer:
    def __init__(self, output_dir: Path, fmt: str = "png", dpi: int = 300, theme: str = "light") -> None:
        self.charts_dir = output_dir / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        self.fmt = fmt
        self.dpi = dpi
        self.style = LIGHT_STYLE if theme == "light" else DARK_STYLE

    def _save(self, name: str) -> Path:
        path = self.charts_dir / f"{name}.{self.fmt}"
        plt.tight_layout()
        plt.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close()
        return path

    # -------------------------------------------------------------------------
    # Distribution charts
    # -------------------------------------------------------------------------
    def distribution_charts(
        self, df: pd.DataFrame, result: DistributionResult
    ) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        with plt.style.context(self.style):
            for col_stats in result.numeric:
                col = col_stats.name
                series = df[col].dropna()
                if len(series) < 2:
                    continue

                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
                fig.suptitle(f"Distribution — {col}", fontsize=13)

                # Histogram + KDE
                sns.histplot(series, ax=ax1, kde=True, bins="auto", color="#4C72B0")
                ax1.set_title("Histogram + KDE")
                ax1.set_xlabel(col)

                # Box plot
                ax2.boxplot(series, vert=True, patch_artist=True,
                            boxprops={"facecolor": "#4C72B0", "alpha": 0.6})
                ax2.set_title("Box Plot")
                ax2.set_ylabel(col)
                ax2.set_xticks([])

                slug = _slug(col)
                paths[f"dist_{slug}"] = self._save(f"distribution_{slug}")

            for col_stats in result.categorical:
                if not col_stats.top_values:
                    continue
                labels = [v[0][:20] for v in col_stats.top_values]
                counts = [v[1] for v in col_stats.top_values]

                fig, ax = plt.subplots(figsize=(10, 5))
                ax.barh(labels[::-1], counts[::-1], color="#DD8452")
                ax.set_title(f"Top Values — {col_stats.name}")
                ax.set_xlabel("Count")
                slug = _slug(col_stats.name)
                paths[f"cat_{slug}"] = self._save(f"categorical_{slug}")

        return paths

    # -------------------------------------------------------------------------
    # Correlation charts
    # -------------------------------------------------------------------------
    def correlation_charts(self, result: CorrelationResult, max_cols: int = 8) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        with plt.style.context(self.style):
            for label, matrix in [("pearson", result.pearson), ("spearman", result.spearman)]:
                if matrix is None or matrix.shape[0] < 2:
                    continue
                sub = matrix.iloc[:max_cols, :max_cols]
                mask = np.triu(np.ones_like(sub, dtype=bool), k=1)
                fig, ax = plt.subplots(figsize=(min(14, sub.shape[0] + 2), min(12, sub.shape[0] + 1)))
                sns.heatmap(
                    sub, mask=mask, annot=sub.shape[0] <= 15, fmt=".2f",
                    cmap="RdBu_r", center=0, vmin=-1, vmax=1,
                    linewidths=0.3, ax=ax,
                )
                ax.set_title(f"{label.capitalize()} Correlation Matrix")
                paths[f"corr_{label}"] = self._save(f"correlation_{label}")

            # Top-10 strongest pairs bar
            if result.strong_pairs:
                pairs = result.strong_pairs[:10]
                labels_p = [f"{a}\n{b}" for a, b, _, _ in pairs]
                values = [r for _, _, r, _ in pairs]
                colors = ["#DD4949" if v > 0 else "#4C72B0" for v in values]
                fig, ax = plt.subplots(figsize=(10, max(4, len(pairs) * 0.6)))
                ax.barh(labels_p[::-1], values[::-1], color=colors[::-1])
                ax.axvline(0, color="black", linewidth=0.8)
                ax.set_xlabel("Pearson r")
                ax.set_title("Strongest Correlations (|r| ≥ 0.7)")
                paths["corr_top"] = self._save("correlation_top_pairs")

        return paths

    # -------------------------------------------------------------------------
    # Missing value charts
    # -------------------------------------------------------------------------
    def missing_charts(self, result: MissingResult) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        with plt.style.context(self.style):
            # Per-column bar chart (only columns with any missing)
            cols_with_missing = [c for c in result.columns if c.missing_count > 0]
            if cols_with_missing:
                sorted_cols = sorted(cols_with_missing, key=lambda c: -c.missing_pct)
                labels = [c.name[:30] for c in sorted_cols]
                pcts = [c.missing_pct * 100 for c in sorted_cols]

                fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.45)))
                bars = ax.barh(labels[::-1], pcts[::-1], color="#DD8452")
                ax.axvline(50, color="red", linestyle="--", linewidth=0.8, alpha=0.5)
                ax.set_xlabel("Missing (%)")
                ax.set_title("Missing Values per Column")
                for bar, pct in zip(bars[::-1], pcts[::-1]):
                    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                            f"{pct:.1f}%", va="center", fontsize=8)
                paths["missing_bar"] = self._save("missing_bar")

        return paths

    # -------------------------------------------------------------------------
    # Outlier charts
    # -------------------------------------------------------------------------
    def outlier_charts(self, df: pd.DataFrame, result: OutlierResult) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        with plt.style.context(self.style):
            for col_out in result.columns:
                col = col_out.name
                if col not in df.columns:
                    continue
                series = df[col].dropna()
                if len(series) < 4:
                    continue

                arr = series.to_numpy(dtype=float)
                q1, q3 = np.percentile(arr, [25, 75])
                iqr = q3 - q1
                low = q1 - 1.5 * iqr
                high = q3 + 1.5 * iqr
                is_outlier = (arr < low) | (arr > high)

                fig, ax = plt.subplots(figsize=(8, 4))
                ax.scatter(range(len(arr)), arr, c=np.where(is_outlier, "#DD4949", "#4C72B0"),
                           alpha=0.5, s=10)
                ax.axhline(low, color="orange", linestyle="--", linewidth=0.8, label="IQR fence")
                ax.axhline(high, color="orange", linestyle="--", linewidth=0.8)
                ax.set_title(f"Outliers — {col} (IQR fenced)")
                ax.set_xlabel("Index")
                ax.set_ylabel(col)
                ax.legend(fontsize=8)
                slug = _slug(col)
                paths[f"outlier_{slug}"] = self._save(f"outlier_{slug}")

            # Method comparison summary bar
            if result.columns:
                names = [c.name[:20] for c in result.columns]
                iqr_counts = [c.iqr_count for c in result.columns]
                zscore_counts = [c.zscore_count for c in result.columns]
                mz_counts = [c.mzscore_count for c in result.columns]

                x = np.arange(len(names))
                w = 0.25
                fig, ax = plt.subplots(figsize=(max(8, len(names) * 0.9), 5))
                ax.bar(x - w, iqr_counts, w, label="IQR", color="#4C72B0")
                ax.bar(x, zscore_counts, w, label="Z-score", color="#DD8452")
                ax.bar(x + w, mz_counts, w, label="Modified Z", color="#55A868")
                ax.set_xticks(x)
                ax.set_xticklabels(names, rotation=45, ha="right")
                ax.set_ylabel("Outlier count")
                ax.set_title("Outlier Counts per Column — Method Comparison")
                ax.legend()
                paths["outlier_comparison"] = self._save("outlier_comparison")

        return paths


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_")[:40]
