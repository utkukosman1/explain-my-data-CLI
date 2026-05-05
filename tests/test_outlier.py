import numpy as np
import pandas as pd

from emd.analysis import OutlierAnalyzer


def test_known_outliers() -> None:
    # Use normally distributed base so MAD > 0, then add extreme outliers
    rng = np.random.default_rng(0)
    base = rng.normal(50, 5, 100)
    base[0] = 1000.0   # extreme high outlier
    base[1] = -900.0   # extreme low outlier
    df = pd.DataFrame({"x": base})
    result = OutlierAnalyzer().analyze(df)
    col = result.columns[0]
    assert col.iqr_count >= 2
    assert col.zscore_count >= 2
    assert col.mzscore_count >= 2


def test_no_outliers_in_normal_data(simple_df: "pd.DataFrame") -> None:
    result = OutlierAnalyzer().analyze(simple_df)
    # Normal-ish data — expect very few outliers, not majority
    for col in result.columns:
        assert col.iqr_pct < 0.20


def test_methods_used_default() -> None:
    df = pd.DataFrame({"a": range(50)})
    result = OutlierAnalyzer().analyze(df)
    assert "iqr" in result.methods_used
    assert "zscore" in result.methods_used
    assert "mzscore" in result.methods_used
