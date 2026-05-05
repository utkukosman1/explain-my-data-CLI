from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DATASETS_DIR = Path(__file__).parent.parent / "datasets"


@pytest.fixture
def simple_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 200
    return pd.DataFrame({
        "age": rng.normal(35, 10, n),
        "income": rng.exponential(50000, n),
        "score": rng.uniform(0, 100, n),
        "category": rng.choice(["A", "B", "C"], n),
        "flag": rng.choice(["yes", "no"], n),
    })


@pytest.fixture
def df_with_missing(simple_df: pd.DataFrame) -> pd.DataFrame:
    df = simple_df.copy()
    rng = np.random.default_rng(0)
    df.loc[rng.choice(df.index, 30, replace=False), "age"] = np.nan
    df.loc[rng.choice(df.index, 80, replace=False), "income"] = np.nan
    return df


@pytest.fixture
def iris_df() -> pd.DataFrame:
    path = DATASETS_DIR / "iris.csv"
    if path.exists():
        return pd.read_csv(path)
    pytest.skip("iris.csv not found in datasets/")


@pytest.fixture
def titanic_df() -> pd.DataFrame:
    path = DATASETS_DIR / "titanic.csv"
    if path.exists():
        return pd.read_csv(path)
    pytest.skip("titanic.csv not found in datasets/")
