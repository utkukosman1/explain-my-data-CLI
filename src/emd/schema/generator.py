from __future__ import annotations

import pandas as pd

from emd.schema.contract import ColumnRule, GlobalRule, SchemaContract


class ContractGenerator:
    CARDINALITY_THRESHOLD = 20
    MIN_ROWS_BUFFER = 0.8
    MISSING_PCT_BUFFER = 1.5

    @classmethod
    def from_dataframe(
        cls, df: pd.DataFrame, name: str = "", description: str = ""
    ) -> SchemaContract:
        columns: dict[str, ColumnRule] = {}
        for col in df.columns:
            columns[col] = cls._make_column_rule(df[col])

        actual_dup_pct = float(df.duplicated().mean() * 100) if len(df) > 0 else 0.0
        max_dup = round(min(actual_dup_pct * 1.5 + 1.0, 100.0), 1)

        global_rules = GlobalRule(
            min_rows=int(max(1, int(len(df) * cls.MIN_ROWS_BUFFER))),
            max_duplicate_pct=float(max_dup),
            extra_columns="warn",
        )

        return SchemaContract(
            version="1.0",
            name=name,
            description=description,
            global_rules=global_rules,
            columns=columns,
        )

    @classmethod
    def _infer_dtype(cls, series: pd.Series) -> str:
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"
        return "categorical"

    @classmethod
    def _make_column_rule(cls, series: pd.Series) -> ColumnRule:
        dtype = cls._infer_dtype(series)
        actual_missing_pct = series.isna().mean() * 100

        if actual_missing_pct == 0.0:
            max_missing_pct = 0.0
        else:
            max_missing_pct = round(
                float(min(actual_missing_pct * cls.MISSING_PCT_BUFFER, 100.0)), 1
            )

        if dtype == "numeric":
            non_null = series.dropna()
            if len(non_null) == 0:
                return ColumnRule(dtype=dtype, required=True, max_missing_pct=100.0)

            actual_min = float(non_null.min())
            actual_max = float(non_null.max())

            if actual_min == actual_max == 0.0:
                buffered_min = -0.1
                buffered_max = 0.1
            else:
                buffered_min = actual_min - abs(actual_min) * 0.1
                buffered_max = actual_max + abs(actual_max) * 0.1

            buffered_min = round(buffered_min, 6)
            buffered_max = round(buffered_max, 6)

            return ColumnRule(
                dtype=dtype,
                required=True,
                min=buffered_min,
                max=buffered_max,
                max_missing_pct=max_missing_pct,
            )

        if dtype == "categorical":
            non_null = series.dropna()
            unique_count = int(non_null.nunique())
            allowed: list[str] | None = None
            if unique_count <= cls.CARDINALITY_THRESHOLD and unique_count > 0:
                allowed = sorted(str(v) for v in non_null.unique())
            return ColumnRule(
                dtype=dtype,
                required=True,
                max_missing_pct=max_missing_pct,
                allowed_values=allowed,
            )

        # datetime
        return ColumnRule(dtype=dtype, required=True, max_missing_pct=max_missing_pct)
