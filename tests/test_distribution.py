import math

import pandas as pd
import pytest

from emd.analysis import DistributionAnalyzer


def test_numeric_stats_basic(simple_df: "pd.DataFrame") -> None:
    result = DistributionAnalyzer().analyze(simple_df)
    names = [s.name for s in result.numeric]
    assert "age" in names
    assert "income" in names


def test_numeric_stats_values(simple_df: "pd.DataFrame") -> None:
    result = DistributionAnalyzer().analyze(simple_df)
    age = next(s for s in result.numeric if s.name == "age")
    assert age.count == 200
    assert age.null_count == 0
    assert 20 < age.mean < 50
    assert age.std > 0
    assert age.p25 < age.p50 < age.p75


def test_normality_test_present(simple_df: "pd.DataFrame") -> None:
    result = DistributionAnalyzer().analyze(simple_df)
    age = next(s for s in result.numeric if s.name == "age")
    assert age.normality_test in ("Shapiro-Wilk", "D'Agostino-Pearson")
    assert age.normality_pvalue is not None
    assert 0 <= age.normality_pvalue <= 1


def test_categorical_stats(simple_df: "pd.DataFrame") -> None:
    result = DistributionAnalyzer().analyze(simple_df)
    cat = next(s for s in result.categorical if s.name == "category")
    assert cat.unique_count == 3
    assert cat.entropy > 0
    assert len(cat.top_values) <= 10


def test_with_missing_values(df_with_missing: "pd.DataFrame") -> None:
    result = DistributionAnalyzer().analyze(df_with_missing)
    age = next(s for s in result.numeric if s.name == "age")
    assert age.null_count == 30
    assert not math.isnan(age.mean)
