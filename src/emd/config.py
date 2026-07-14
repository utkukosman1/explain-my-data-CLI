from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReportConfig:
    """Options threaded through the `analyze` CLI pipeline.

    Every field here is consumed somewhere downstream — if you add one, wire it
    through in emd/cli/analyze.py (the web backend builds its own options dict
    and does not use this class).
    """

    output_dir: str = "./reports"
    chart_format: str = "png"
    chart_dpi: int = 300
    theme: str = "light"
    skip_correlation: bool = False
    skip_outlier: bool = False
    use_iforest: bool = False
    iqr_multiplier: float = 1.5
    iqr_extreme_multiplier: float = 3.0
    zscore_threshold: float = 3.0
    mzscore_threshold: float = 3.5
    iforest_contamination: str = "auto"
    sample_size: int | None = None
    parse_dates: list[str] = field(default_factory=list)
    drop_cols: list[str] = field(default_factory=list)
    sheet: str | None = None
    output_json: bool = False
    quiet: bool = False
    no_quality_gate: bool = False
    max_pairplot_cols: int = 8
    target: str | None = None
