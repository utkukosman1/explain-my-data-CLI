from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import matplotlib
import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from emd.analysis.correlation import STRONG_CORRELATION_THRESHOLD, CorrelationResult
from emd.analysis.distribution import DistributionResult
from emd.analysis.drift import PSI_MODERATE_THRESHOLD, DriftResult
from emd.analysis.missing import MissingResult
from emd.analysis.outlier import OutlierResult
from emd.analysis.target import TargetResult

matplotlib.use("Agg")  # non-interactive backend

LIGHT_STYLE = "seaborn-v0_8-whitegrid"
DARK_STYLE = "dark_background"


class ChartRenderer:
    def __init__(
        self, output_dir: Path, fmt: str = "png", dpi: int = 300, theme: str = "light"
    ) -> None:
        self.charts_dir = output_dir / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        self.fmt = fmt
        self.dpi = dpi
        self.style = LIGHT_STYLE if theme == "light" else DARK_STYLE
        self.failures: list[str] = []

    def _record_failure(self, label: str, exc: Exception) -> None:
        self.failures.append(f"{label}: {exc}")

    def _save(self, fig: matplotlib.figure.Figure, name: str) -> Path:
        path = self.charts_dir / f"{name}.{self.fmt}"
        fig.tight_layout()
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    def _new_fig(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Create a figure+axes using the configured style, OO API (thread-safe)."""
        with plt.style.context(self.style):
            fig, ax = plt.subplots(*args, **kwargs)
        return fig, ax

    def _new_figs(self, rows: int, cols: int, **kwargs):  # type: ignore[no-untyped-def]
        with plt.style.context(self.style):
            fig, axes = plt.subplots(rows, cols, **kwargs)
        return fig, axes

    # -------------------------------------------------------------------------
    # Distribution charts
    # -------------------------------------------------------------------------
    def distribution_charts(
        self, df: pd.DataFrame, result: DistributionResult
    ) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        seen: dict[str, int] = {}

        def _render_numeric(col_stats):  # type: ignore[no-untyped-def]
            col = col_stats.name
            try:
                series = df[col].dropna()
                if len(series) < 2:
                    return None, None
                fig, (ax1, ax2) = self._new_figs(1, 2, figsize=(12, 4))
                fig.suptitle(f"Distribution — {col}", fontsize=13)
                sns.histplot(series, ax=ax1, kde=True, bins="auto", color="#4C72B0")
                ax1.set_title("Histogram + KDE")
                ax1.set_xlabel(col)
                ax2.boxplot(series, vert=True, patch_artist=True,
                            boxprops={"facecolor": "#4C72B0", "alpha": 0.6})
                ax2.set_title("Box Plot")
                ax2.set_ylabel(col)
                ax2.set_xticks([])
                return f"dist:{col}", self._save(fig, f"distribution_{_slug(col, seen)}")
            except Exception as exc:
                self._record_failure(f"distribution chart for '{col}'", exc)
                return None, None

        def _render_categorical(col_stats):  # type: ignore[no-untyped-def]
            if not col_stats.top_values:
                return None, None
            try:
                labels = [_truncate(v[0], 20) for v in col_stats.top_values]
                counts = [v[1] for v in col_stats.top_values]
                fig, ax = self._new_fig(figsize=(10, 5))
                ax.barh(labels[::-1], counts[::-1], color="#DD8452")
                ax.set_title(f"Top Values — {col_stats.name}")
                ax.set_xlabel("Count")
                slug = _slug(col_stats.name, seen)
                return f"cat:{col_stats.name}", self._save(fig, f"categorical_{slug}")
            except Exception as exc:
                self._record_failure(f"categorical chart for '{col_stats.name}'", exc)
                return None, None

        tasks = (
            [lambda cs=cs: _render_numeric(cs) for cs in result.numeric]
            + [lambda cs=cs: _render_categorical(cs) for cs in result.categorical]
        )
        with ThreadPoolExecutor() as executor:
            for key, path in executor.map(lambda fn: fn(), tasks):
                if key is not None:
                    paths[key] = path
        return paths

    # -------------------------------------------------------------------------
    # Correlation charts
    # -------------------------------------------------------------------------
    def correlation_charts(self, result: CorrelationResult, max_cols: int = 8) -> dict[str, Path]:
        paths: dict[str, Path] = {}

        for label, matrix in [("pearson", result.pearson), ("spearman", result.spearman)]:
            if matrix is None or matrix.shape[0] < 2:
                continue
            try:
                sub = matrix.iloc[:max_cols, :max_cols]
                mask = np.triu(np.ones_like(sub, dtype=bool), k=1)
                figsize = (min(14, sub.shape[0] + 2), min(12, sub.shape[0] + 1))
                fig, ax = self._new_fig(figsize=figsize)
                sns.heatmap(
                    sub, mask=mask, annot=sub.shape[0] <= 15, fmt=".2f",
                    cmap="RdBu_r", center=0, vmin=-1, vmax=1,
                    linewidths=0.3, ax=ax,
                )
                ax.set_title(f"{label.capitalize()} Correlation Matrix")
                paths[f"corr_{label}"] = self._save(fig, f"correlation_{label}")
            except Exception as exc:
                self._record_failure(f"{label} correlation heatmap", exc)

        if result.strong_pairs:
            try:
                pairs = result.strong_pairs[:10]
                labels_p = [f"{a}\n{b}" for a, b, _, _ in pairs]
                values = [r for _, _, r, _ in pairs]
                colors = ["#DD4949" if v > 0 else "#4C72B0" for v in values]
                fig, ax = self._new_fig(figsize=(10, max(4, len(pairs) * 0.6)))
                ax.barh(labels_p[::-1], values[::-1], color=colors[::-1])
                ax.axvline(0, color="black", linewidth=0.8)
                ax.set_xlabel("Pearson r")
                ax.set_title(f"Strongest Correlations (|r| ≥ {STRONG_CORRELATION_THRESHOLD})")
                paths["corr_top"] = self._save(fig, "correlation_top_pairs")
            except Exception as exc:
                self._record_failure("strongest-correlations chart", exc)

        return paths

    # -------------------------------------------------------------------------
    # Missing value charts
    # -------------------------------------------------------------------------
    def missing_charts(self, result: MissingResult) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        cols_with_missing = [c for c in result.columns if c.missing_count > 0]
        if cols_with_missing:
            try:
                sorted_cols = sorted(cols_with_missing, key=lambda c: -c.missing_pct)
                labels = [_truncate(c.name, 30) for c in sorted_cols]
                pcts = [c.missing_pct * 100 for c in sorted_cols]

                fig, ax = self._new_fig(figsize=(10, max(4, len(labels) * 0.45)))
                bars = ax.barh(labels[::-1], pcts[::-1], color="#DD8452")
                ax.axvline(50, color="red", linestyle="--", linewidth=0.8, alpha=0.5,
                           label="50% threshold")
                ax.set_xlabel("Missing (%)")
                ax.set_title("Missing Values per Column")
                ax.legend(fontsize=8)
                for bar, pct in zip(bars[::-1], pcts[::-1], strict=True):
                    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                            f"{pct:.1f}%", va="center", fontsize=8)
                paths["missing_bar"] = self._save(fig, "missing_bar")
            except Exception as exc:
                self._record_failure("missing-values chart", exc)

        return paths

    # -------------------------------------------------------------------------
    # Outlier charts
    # -------------------------------------------------------------------------
    def outlier_charts(self, df: pd.DataFrame, result: OutlierResult) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        seen: dict[str, int] = {}

        def _render_col(col_out):  # type: ignore[no-untyped-def]
            col = col_out.name
            if col not in df.columns:
                return None, None
            try:
                series = df[col].dropna()
                if len(series) < 4:
                    return None, None
                arr = series.to_numpy(dtype=float)
                q1, q3 = np.percentile(arr, [25, 75])
                iqr = q3 - q1
                low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                is_outlier = (arr < low) | (arr > high)
                fig, ax = self._new_fig(figsize=(8, 4))
                ax.scatter(range(len(arr)), arr, c=np.where(is_outlier, "#DD4949", "#4C72B0"),
                           alpha=0.5, s=10)
                ax.axhline(low, color="orange", linestyle="--", linewidth=0.8, label="IQR fence")
                ax.axhline(high, color="orange", linestyle="--", linewidth=0.8)
                ax.set_title(f"Outliers — {col} (IQR fenced)")
                ax.set_xlabel("Index")
                ax.set_ylabel(col)
                ax.legend(fontsize=8)
                return f"outlier:{col}", self._save(fig, f"outlier_{_slug(col, seen)}")
            except Exception as exc:
                self._record_failure(f"outlier chart for '{col}'", exc)
                return None, None

        with ThreadPoolExecutor() as executor:
            for key, path in executor.map(_render_col, result.columns):
                if key is not None:
                    paths[key] = path

        if result.columns:
            try:
                names = [_truncate(c.name, 20) for c in result.columns]
                iqr_counts = [c.iqr_count for c in result.columns]
                zscore_counts = [c.zscore_count for c in result.columns]
                mz_counts = [c.mzscore_count for c in result.columns]
                x = np.arange(len(names))
                w = 0.25
                fig, ax = self._new_fig(figsize=(max(8, len(names) * 0.9), 5))
                ax.bar(x - w, iqr_counts, w, label="IQR", color="#4C72B0")
                ax.bar(x, zscore_counts, w, label="Z-score", color="#DD8452")
                ax.bar(x + w, mz_counts, w, label="Modified Z", color="#55A868")
                ax.set_xticks(x)
                ax.set_xticklabels(names, rotation=45, ha="right")
                ax.set_ylabel("Outlier count")
                ax.set_title("Outlier Counts per Column — Method Comparison")
                ax.legend()
                paths["outlier_comparison"] = self._save(fig, "outlier_comparison")
            except Exception as exc:
                self._record_failure("outlier comparison chart", exc)

        return paths

    # -------------------------------------------------------------------------
    # Target variable charts
    # -------------------------------------------------------------------------
    def target_charts(
        self, df: pd.DataFrame, result: TargetResult, top_n: int = 5
    ) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        seen: dict[str, int] = {}
        target_col = result.target_col
        if target_col not in df.columns:
            return paths

        features = [f.feature for f in result.top_features[:top_n] if f.feature in df.columns]
        if not features:
            return paths

        if result.target_type == "categorical":
            target_series = df[target_col].astype(str)
            n_classes = target_series.nunique()
            palette = sns.color_palette("tab10", n_classes)

            def _render_cat_feat(feat):  # type: ignore[no-untyped-def]
                try:
                    if not pd.api.types.is_numeric_dtype(df[feat]):
                        return None, None
                    fig, (ax1, ax2) = self._new_figs(1, 2, figsize=(12, 4))
                    fig.suptitle(f"{feat} by {target_col}", fontsize=13)
                    sns.histplot(data=df, x=feat, hue=target_col, ax=ax1,
                                 kde=True, bins="auto", palette=palette, alpha=0.5)
                    ax1.set_title("Distribution by Target")
                    groups = [df[feat][df[target_col].astype(str) == cls].dropna()
                              for cls in target_series.unique()]
                    labels = [str(cls) for cls in target_series.unique()]
                    ax2.boxplot(groups, patch_artist=True)
                    ax2.set_xticklabels(labels)
                    ax2.set_title("Box Plot by Target Class")
                    ax2.set_xlabel(target_col)
                    fig.autofmt_xdate(rotation=30)
                    slug = _slug(feat, seen)
                    return f"target_hist:{feat}", self._save(fig, f"target_hist_{slug}")
                except Exception as exc:
                    self._record_failure(f"target chart for '{feat}'", exc)
                    return None, None

            with ThreadPoolExecutor() as executor:
                for key, path in executor.map(_render_cat_feat, features):
                    if key is not None:
                        paths[key] = path
        else:
            def _render_num_feat(feat):  # type: ignore[no-untyped-def]
                try:
                    if not pd.api.types.is_numeric_dtype(df[feat]):
                        return None, None
                    combined = df[[feat, target_col]].dropna()
                    if len(combined) < 5:
                        return None, None
                    fig, ax = self._new_fig(figsize=(8, 5))
                    sc = ax.scatter(combined[feat], combined[target_col],
                                   c=combined[target_col], cmap="viridis", alpha=0.5, s=15)
                    fig.colorbar(sc, ax=ax, label=target_col)
                    ax.set_xlabel(feat)
                    ax.set_ylabel(target_col)
                    ax.set_title(f"{feat} vs {target_col}")
                    slug = _slug(feat, seen)
                    return f"target_scatter:{feat}", self._save(fig, f"target_scatter_{slug}")
                except Exception as exc:
                    self._record_failure(f"target chart for '{feat}'", exc)
                    return None, None

            with ThreadPoolExecutor() as executor:
                for key, path in executor.map(_render_num_feat, features):
                    if key is not None:
                        paths[key] = path

        return paths

    # -------------------------------------------------------------------------
    # Drift comparison charts
    # -------------------------------------------------------------------------
    def drift_charts(
        self, df_ref: pd.DataFrame, df_cur: pd.DataFrame, result: DriftResult
    ) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        seen: dict[str, int] = {}

        def _render_drift_col(col_drift):  # type: ignore[no-untyped-def]
            if not col_drift.drift_detected:
                return None, None
            col = col_drift.name
            if col not in df_ref.columns or col not in df_cur.columns:
                return None, None

            try:
                if col_drift.col_type == "numeric":
                    ref_vals = df_ref[col].dropna()
                    cur_vals = df_cur[col].dropna()
                    if len(ref_vals) < 2 or len(cur_vals) < 2:
                        return None, None
                    fig, ax = self._new_fig(figsize=(8, 4))
                    ax.hist(ref_vals, bins=30, alpha=0.5, color="#4C72B0",
                            label="Reference", density=True)
                    ax.hist(cur_vals, bins=30, alpha=0.5, color="#DD8452",
                            label="Current", density=True)
                    ax.set_title(f"Drift — {col} (PSI={col_drift.psi:.3f})")
                    ax.set_xlabel(col)
                    ax.set_ylabel("Density")
                    ax.legend()
                else:
                    ref_vals = df_ref[col].dropna().astype(str)
                    cur_vals = df_cur[col].dropna().astype(str)
                    all_cats = sorted(set(ref_vals.unique()) | set(cur_vals.unique()))[:15]
                    ref_pct = ref_vals.value_counts(normalize=True).reindex(all_cats, fill_value=0)
                    cur_pct = cur_vals.value_counts(normalize=True).reindex(all_cats, fill_value=0)
                    x = np.arange(len(all_cats))
                    w = 0.35
                    fig, ax = self._new_fig(figsize=(max(8, len(all_cats) * 0.7), 4))
                    ax.bar(x - w / 2, ref_pct.values, w, label="Reference",
                           color="#4C72B0", alpha=0.8)
                    ax.bar(x + w / 2, cur_pct.values, w, label="Current",
                           color="#DD8452", alpha=0.8)
                    ax.set_xticks(x)
                    ax.set_xticklabels(all_cats, rotation=45, ha="right")
                    ax.set_title(f"Drift — {col} (categorical)")
                    ax.set_ylabel("Proportion")
                    ax.legend()

                slug = _slug(col, seen)
                return f"drift:{col}", self._save(fig, f"drift_{slug}")
            except Exception as exc:
                self._record_failure(f"drift chart for '{col}'", exc)
                return None, None

        with ThreadPoolExecutor() as executor:
            for key, path in executor.map(_render_drift_col, result.columns):
                if key is not None:
                    paths[key] = path

        numeric_drifts = [
            c for c in result.columns if c.col_type == "numeric" and c.psi is not None
        ]
        if numeric_drifts:
            try:
                names = [_truncate(c.name, 25) for c in numeric_drifts]
                psi_vals = [c.psi for c in numeric_drifts]
                colors = ["#DD4949" if c.drift_detected else "#55A868" for c in numeric_drifts]
                fig, ax = self._new_fig(figsize=(max(8, len(names) * 0.8), 5))
                ax.bar(names, psi_vals, color=colors)
                ax.axhline(result.psi_threshold, color="red", linestyle="--",
                           linewidth=1.2, label=f"Threshold ({result.psi_threshold})")
                ax.axhline(PSI_MODERATE_THRESHOLD, color="orange", linestyle=":", linewidth=1.0,
                           label=f"Moderate ({PSI_MODERATE_THRESHOLD})")
                ax.set_ylabel("PSI")
                ax.set_title("Population Stability Index per Column")
                ax.set_xticks(range(len(names)))
                ax.set_xticklabels(names, rotation=45, ha="right")
                ax.legend()
                paths["drift_summary"] = self._save(fig, "drift_psi_summary")
            except Exception as exc:
                self._record_failure("PSI summary chart", exc)

        return paths


def _slug(name: str, seen: dict[str, int]) -> str:
    """Collision-safe filename slug. Pass the same `seen` dict within one render call."""
    base = "".join(c if c.isalnum() else "_" for c in name).strip("_")[:40] or "col"
    count = seen.get(base, 0)
    seen[base] = count + 1
    return base if count == 0 else f"{base}_{count}"


def _truncate(label: str, max_len: int) -> str:
    """Truncate a chart label, marking truncation with an ellipsis instead of cutting silently."""
    return label if len(label) <= max_len else label[: max_len - 1] + "…"
