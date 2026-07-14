import numpy as np
import pandas as pd
import pytest

from emd.analysis.drift import DriftAnalyzer


@pytest.fixture
def df_no_drift() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(0)
    ref = pd.DataFrame({
        "a": rng.normal(0, 1, 500), "b": rng.normal(10, 2, 500),
        "cat": rng.choice(["X", "Y"], 500),
    })
    cur = pd.DataFrame({
        "a": rng.normal(0, 1, 400), "b": rng.normal(10, 2, 400),
        "cat": rng.choice(["X", "Y"], 400),
    })
    return ref, cur


@pytest.fixture
def df_with_drift() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(1)
    ref = pd.DataFrame({"a": rng.normal(0, 1, 500), "b": rng.normal(10, 2, 500)})
    # Large mean shift on 'a', std change on 'b'
    cur = pd.DataFrame({"a": rng.normal(5, 1, 500), "b": rng.normal(10, 8, 500)})
    return ref, cur


def test_no_drift_detected(df_no_drift: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    ref, cur = df_no_drift
    result = DriftAnalyzer().analyze(ref, cur)
    # With same distribution, overall drift should be absent or minimal
    assert result.drift_fraction < 0.5


def test_drift_detected_on_shifted_data(df_with_drift: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    ref, cur = df_with_drift
    result = DriftAnalyzer().analyze(ref, cur)
    assert result.overall_drift
    assert "a" in result.drifted_columns


def test_shapes_recorded(df_no_drift: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    ref, cur = df_no_drift
    result = DriftAnalyzer().analyze(ref, cur)
    assert result.reference_shape == ref.shape
    assert result.current_shape == cur.shape


def test_missing_and_new_columns() -> None:
    ref = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    cur = pd.DataFrame({"a": [1, 2, 3], "c": [7, 8, 9]})
    result = DriftAnalyzer().analyze(ref, cur)
    assert "b" in result.missing_in_current
    assert "c" in result.new_in_current


def test_psi_values_non_negative(df_with_drift: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    ref, cur = df_with_drift
    result = DriftAnalyzer().analyze(ref, cur)
    for col in result.columns:
        if col.psi is not None:
            assert col.psi >= 0.0


def test_custom_threshold() -> None:
    rng = np.random.default_rng(2)
    ref = pd.DataFrame({"x": rng.normal(0, 1, 300)})
    cur = pd.DataFrame({"x": rng.normal(0.5, 1, 300)})
    # With low threshold, drift should be detected
    result_strict = DriftAnalyzer(psi_threshold=0.05).analyze(ref, cur)
    result_loose = DriftAnalyzer(psi_threshold=0.5).analyze(ref, cur)
    # Strict should detect at least as much drift as loose
    assert result_strict.drift_fraction >= result_loose.drift_fraction


def test_column_count(df_no_drift: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    ref, cur = df_no_drift
    result = DriftAnalyzer().analyze(ref, cur)
    assert len(result.columns) == len(ref.columns)
