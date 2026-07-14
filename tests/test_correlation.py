import numpy as np
import pandas as pd

from emd.analysis import CorrelationAnalyzer


def test_perfect_correlation() -> None:
    df = pd.DataFrame({"a": range(50), "b": [x * 2 for x in range(50)]})
    result = CorrelationAnalyzer().analyze(df)
    assert result.pearson is not None
    assert abs(result.pearson.loc["a", "b"] - 1.0) < 1e-6


def test_strong_pairs_detected() -> None:
    rng = np.random.default_rng(42)
    x = rng.normal(0, 1, 100)
    df = pd.DataFrame({"x": x, "y": x + rng.normal(0, 0.01, 100), "z": rng.normal(0, 1, 100)})
    result = CorrelationAnalyzer().analyze(df)
    assert len(result.strong_pairs) > 0
    assert result.strong_pairs[0][2] > 0.7


def test_cramers_v_returned(simple_df: "pd.DataFrame") -> None:
    result = CorrelationAnalyzer().analyze(simple_df)
    assert result.cramers_v is not None
    assert result.cramers_v.shape[0] == 2  # category, flag


def test_no_correlation_with_single_numeric() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "cat": ["x", "y", "z"]})
    result = CorrelationAnalyzer().analyze(df)
    assert result.pearson is None
    assert result.spearman is None
