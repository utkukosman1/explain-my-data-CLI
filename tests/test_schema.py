from __future__ import annotations

import numpy as np
import pandas as pd

from emd.schema.contract import ColumnRule, GlobalRule, SchemaContract, load_contract, save_contract
from emd.schema.generator import ContractGenerator
from emd.schema.validator import SchemaValidator

# ---------------------------------------------------------------------------
# Generation tests
# ---------------------------------------------------------------------------

def test_contract_generation_numeric_bounds(simple_df: pd.DataFrame) -> None:
    contract = ContractGenerator.from_dataframe(simple_df)
    rule = contract.columns["age"]
    assert rule.dtype == "numeric"
    assert rule.min is not None and rule.min < simple_df["age"].min()
    assert rule.max is not None and rule.max > simple_df["age"].max()


def test_contract_generation_categorical_allowed_values(simple_df: pd.DataFrame) -> None:
    contract = ContractGenerator.from_dataframe(simple_df)
    rule = contract.columns["category"]
    assert rule.dtype == "categorical"
    assert rule.allowed_values == ["A", "B", "C"]


def test_contract_generation_high_cardinality_no_allowed_values() -> None:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"col": [f"val_{i}" for i in rng.integers(0, 25, 100)]})
    contract = ContractGenerator.from_dataframe(df)
    assert contract.columns["col"].allowed_values is None


def test_contract_global_min_rows(simple_df: pd.DataFrame) -> None:
    contract = ContractGenerator.from_dataframe(simple_df)
    assert contract.global_rules.min_rows == int(200 * 0.8)


def test_yaml_roundtrip(simple_df: pd.DataFrame, tmp_path) -> None:
    contract = ContractGenerator.from_dataframe(simple_df, name="test_dataset")
    out = tmp_path / "schema.yaml"
    save_contract(contract, out)
    loaded = load_contract(out)

    assert loaded.name == "test_dataset"
    assert loaded.version == contract.version
    assert set(loaded.columns.keys()) == set(contract.columns.keys())
    assert loaded.global_rules.min_rows == contract.global_rules.min_rows
    assert loaded.global_rules.extra_columns == contract.global_rules.extra_columns

    for col in contract.columns:
        orig = contract.columns[col]
        back = loaded.columns[col]
        assert back.dtype == orig.dtype
        assert back.required == orig.required
        assert back.max_missing_pct == orig.max_missing_pct
        if orig.allowed_values is not None:
            assert back.allowed_values == orig.allowed_values


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_validation_passes_on_same_data(simple_df: pd.DataFrame) -> None:
    contract = ContractGenerator.from_dataframe(simple_df)
    result = SchemaValidator.validate(simple_df, contract)
    assert result.passed is True
    assert result.violations == []


def test_validation_fails_missing_required_column(simple_df: pd.DataFrame) -> None:
    contract = ContractGenerator.from_dataframe(simple_df)
    df_missing_col = simple_df.drop(columns=["age"])
    result = SchemaValidator.validate(df_missing_col, contract)
    assert result.passed is False
    required_violations = [
        v for v in result.violations if v.check == "required" and v.column == "age"
    ]
    assert len(required_violations) == 1
    assert required_violations[0].severity == "error"


def test_validation_fails_numeric_out_of_range() -> None:
    contract = SchemaContract(
        columns={"value": ColumnRule(dtype="numeric", min=0.0, max=100.0)},
    )
    df = pd.DataFrame({"value": [50.0, 200.0]})
    result = SchemaValidator.validate(df, contract)
    assert result.passed is False
    max_violations = [v for v in result.violations if v.check == "max" and v.column == "value"]
    assert len(max_violations) == 1
    assert max_violations[0].severity == "error"


def test_validation_warns_unexpected_categorical_value() -> None:
    contract = SchemaContract(
        columns={"cat": ColumnRule(dtype="categorical", allowed_values=["A", "B"])},
    )
    df = pd.DataFrame({"cat": ["A", "B", "C"]})
    result = SchemaValidator.validate(df, contract)
    warnings = [v for v in result.violations if v.check == "allowed_values"]
    assert len(warnings) == 1
    assert warnings[0].severity == "warning"
    assert result.passed is True  # warnings don't fail by default


def test_validation_strict_mode_promotes_warnings() -> None:
    contract = SchemaContract(
        columns={"cat": ColumnRule(dtype="categorical", allowed_values=["A", "B"])},
    )
    df = pd.DataFrame({"cat": ["A", "B", "C"]})
    result = SchemaValidator.validate(df, contract, strict=True)
    assert result.passed is False
    assert all(v.severity == "error" for v in result.violations)


def test_validation_global_min_rows() -> None:
    contract = SchemaContract(global_rules=GlobalRule(min_rows=500))
    df = pd.DataFrame({"x": range(10)})
    result = SchemaValidator.validate(df, contract)
    assert result.passed is False
    row_violations = [v for v in result.violations if v.check == "min_rows"]
    assert len(row_violations) == 1
    assert row_violations[0].column == "__global__"


def test_validation_extra_column_warn() -> None:
    contract = SchemaContract(
        global_rules=GlobalRule(extra_columns="warn"),
        columns={"a": ColumnRule(dtype="numeric")},
    )
    df = pd.DataFrame({"a": [1.0], "b": [2.0]})
    result = SchemaValidator.validate(df, contract)
    extra_violations = [
        v for v in result.violations if v.check == "extra_column" and v.column == "b"
    ]
    assert len(extra_violations) == 1
    assert extra_violations[0].severity == "warning"
    assert result.passed is True  # still passes — only a warning


def test_validation_missing_pct_exceeded(df_with_missing: pd.DataFrame) -> None:
    contract = SchemaContract(
        columns={"income": ColumnRule(dtype="numeric", max_missing_pct=0.0)},
    )
    result = SchemaValidator.validate(df_with_missing, contract)
    miss_violations = [
        v for v in result.violations if v.check == "max_missing_pct" and v.column == "income"
    ]
    assert len(miss_violations) == 1
    assert miss_violations[0].severity == "error"


def test_validation_dtype_mismatch_skips_further_checks() -> None:
    contract = SchemaContract(
        columns={"col": ColumnRule(dtype="numeric", min=0.0, max=100.0)},
    )
    df = pd.DataFrame({"col": ["a", "b", "c"]})
    result = SchemaValidator.validate(df, contract)
    dtype_violations = [v for v in result.violations if v.check == "dtype"]
    assert len(dtype_violations) == 1
    # min/max should NOT produce additional violations
    other = [v for v in result.violations if v.check in ("min", "max")]
    assert len(other) == 0


def test_contract_generation_zero_missing_stays_zero() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    contract = ContractGenerator.from_dataframe(df)
    assert contract.columns["x"].max_missing_pct == 0.0
