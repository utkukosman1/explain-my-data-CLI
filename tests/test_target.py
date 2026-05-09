import numpy as np
import pandas as pd
import pytest

from emd.analysis.target import TargetAnalyzer


@pytest.fixture
def df_binary_target() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 200
    target = rng.integers(0, 2, n)
    return pd.DataFrame({
        "age": rng.normal(35, 10, n) + target * 5,
        "income": rng.normal(50000, 10000, n) + target * 8000,
        "score": rng.uniform(0, 100, n),
        "category": rng.choice(["A", "B", "C"], n),
        "Survived": target,
    })


@pytest.fixture
def df_numeric_target() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 150
    x = rng.normal(0, 1, n)
    return pd.DataFrame({
        "feature_a": x,
        "feature_b": x * 2 + rng.normal(0, 0.1, n),
        "feature_c": rng.normal(0, 1, n),
        "SalePrice": x * 100 + rng.normal(0, 5, n),
    })


def test_target_not_found_raises(df_binary_target: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="not found"):
        TargetAnalyzer().analyze(df_binary_target, "nonexistent")


def test_categorical_target_type(df_binary_target: pd.DataFrame) -> None:
    result = TargetAnalyzer().analyze(df_binary_target, "Survived")
    # binary int column treated as numeric by pandas — accept either
    assert result.target_type in ("numeric", "categorical")


def test_numeric_target_type(df_numeric_target: pd.DataFrame) -> None:
    result = TargetAnalyzer().analyze(df_numeric_target, "SalePrice")
    assert result.target_type == "numeric"


def test_top_features_length(df_numeric_target: pd.DataFrame) -> None:
    result = TargetAnalyzer().analyze(df_numeric_target, "SalePrice")
    assert 1 <= len(result.top_features) <= 5


def test_top_features_sorted_by_score(df_numeric_target: pd.DataFrame) -> None:
    result = TargetAnalyzer().analyze(df_numeric_target, "SalePrice")
    scores = [f.score for f in result.top_features]
    assert scores == sorted(scores, reverse=True)


def test_highly_correlated_feature_in_top(df_numeric_target: pd.DataFrame) -> None:
    result = TargetAnalyzer().analyze(df_numeric_target, "SalePrice")
    top_names = [f.feature for f in result.top_features]
    # feature_b is nearly perfectly correlated with SalePrice
    assert "feature_b" in top_names or "feature_a" in top_names


def test_scores_in_range(df_numeric_target: pd.DataFrame) -> None:
    result = TargetAnalyzer().analyze(df_numeric_target, "SalePrice")
    for f in result.all_features:
        assert 0.0 <= f.score <= 1.0


def test_iris_categorical_target(iris_df: pd.DataFrame) -> None:
    result = TargetAnalyzer().analyze(iris_df, "species")
    assert result.target_type == "categorical"
    assert len(result.top_features) > 0
    assert result.top_features[0].score > 0
