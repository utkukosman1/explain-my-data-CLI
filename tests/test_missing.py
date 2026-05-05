import pandas as pd

from emd.analysis import MissingAnalyzer


def test_no_missing(simple_df: "pd.DataFrame") -> None:
    result = MissingAnalyzer().analyze(simple_df)
    assert result.total_missing == 0
    assert result.global_missing_pct == 0.0
    assert result.complete_rows == len(simple_df)


def test_with_missing(df_with_missing: "pd.DataFrame") -> None:
    result = MissingAnalyzer().analyze(df_with_missing)
    assert result.total_missing > 0
    age_col = next(c for c in result.columns if c.name == "age")
    assert age_col.missing_count == 30


def test_complete_rows(df_with_missing: "pd.DataFrame") -> None:
    result = MissingAnalyzer().analyze(df_with_missing)
    assert result.complete_rows < len(df_with_missing)
    assert 0 < result.complete_rows_pct < 1
