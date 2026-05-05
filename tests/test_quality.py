import numpy as np
import pandas as pd
import pytest

from emd.quality import QualityChecker, Severity
from emd.quality.checker import DataQualityError


def test_empty_df_raises() -> None:
    df = pd.DataFrame()
    with pytest.raises(DataQualityError):
        QualityChecker().check(df)


def test_empty_df_no_gate() -> None:
    df = pd.DataFrame()
    report = QualityChecker().check(df, no_quality_gate=True)
    assert not report.passed


def test_clean_df_passes(simple_df: "pd.DataFrame") -> None:
    report = QualityChecker().check(simple_df)
    assert report.passed


def test_high_missing_column_warning() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": [np.nan, np.nan, np.nan]})
    report = QualityChecker().check(df, no_quality_gate=True)
    severities = [i.severity for i in report.issues]
    assert Severity.WARNING in severities


def test_duplicate_rows_warning() -> None:
    row = {"a": 1, "b": 2}
    df = pd.DataFrame([row] * 100 + [{"a": 3, "b": 4}])
    report = QualityChecker().check(df, no_quality_gate=True)
    checks = [i.check for i in report.issues]
    assert any("duplicate" in c.lower() for c in checks)
