from pathlib import Path

import pandas as pd
import pytest

from emd.loader import CSVLoader


def test_csv_loader_basic(tmp_path: Path) -> None:
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("a,b,c\n1,2,3\n4,5,6\n")
    df = CSVLoader().load(csv_file)
    assert df.shape == (2, 3)
    assert list(df.columns) == ["a", "b", "c"]


def test_csv_loader_strips_column_whitespace(tmp_path: Path) -> None:
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(" col1 , col2 \n1,2\n")
    df = CSVLoader().load(csv_file)
    assert "col1" in df.columns
    assert "col2" in df.columns


def test_csv_loader_semicolon_delimiter(tmp_path: Path) -> None:
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("a;b;c\n1;2;3\n")
    df = CSVLoader().load(csv_file)
    assert df.shape == (1, 3)


def test_csv_loader_wrong_extension_raises(tmp_path: Path) -> None:
    bad = tmp_path / "data.parquet"
    bad.write_text("x")
    with pytest.raises(ValueError, match="Unsupported"):
        CSVLoader().load(bad)


def test_csv_loader_iris(iris_df: pd.DataFrame) -> None:
    assert iris_df.shape[0] == 150
    assert "species" in iris_df.columns
