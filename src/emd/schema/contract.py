from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ColumnRule:
    dtype: str  # "numeric" | "categorical" | "datetime" | "any"
    required: bool = True
    min: float | None = None
    max: float | None = None
    max_missing_pct: float | None = None
    allowed_values: list[str] | None = None


@dataclass
class GlobalRule:
    min_rows: int | None = None
    max_duplicate_pct: float | None = None
    extra_columns: str = "warn"  # "warn" | "fail" | "ignore"


@dataclass
class SchemaContract:
    version: str = "1.0"
    name: str = ""
    description: str = ""
    global_rules: GlobalRule = field(default_factory=GlobalRule)
    columns: dict[str, ColumnRule] = field(default_factory=dict)


def _contract_to_dict(contract: SchemaContract) -> dict:
    global_dict: dict = {"extra_columns": contract.global_rules.extra_columns}
    if contract.global_rules.min_rows is not None:
        global_dict["min_rows"] = int(contract.global_rules.min_rows)
    if contract.global_rules.max_duplicate_pct is not None:
        global_dict["max_duplicate_pct"] = float(contract.global_rules.max_duplicate_pct)

    columns_dict: dict = {}
    for col_name, rule in contract.columns.items():
        col_dict: dict = {"dtype": rule.dtype, "required": rule.required}
        if rule.min is not None:
            col_dict["min"] = round(float(rule.min), 6)
        if rule.max is not None:
            col_dict["max"] = round(float(rule.max), 6)
        if rule.max_missing_pct is not None:
            col_dict["max_missing_pct"] = float(rule.max_missing_pct)
        if rule.allowed_values is not None:
            col_dict["allowed_values"] = rule.allowed_values
        columns_dict[col_name] = col_dict

    return {
        "version": contract.version,
        "name": contract.name,
        "description": contract.description,
        "global": global_dict,
        "columns": columns_dict,
    }


def save_contract(contract: SchemaContract, path: Path) -> None:
    data = _contract_to_dict(contract)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def load_contract(path: Path) -> SchemaContract:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    global_data = data.get("global", {})
    global_rules = GlobalRule(
        min_rows=global_data.get("min_rows"),
        max_duplicate_pct=global_data.get("max_duplicate_pct"),
        extra_columns=global_data.get("extra_columns", "warn"),
    )

    columns: dict[str, ColumnRule] = {}
    for col_name, col_data in data.get("columns", {}).items():
        allowed = col_data.get("allowed_values")
        if allowed is not None:
            allowed = [str(v) for v in allowed]
        columns[str(col_name)] = ColumnRule(
            dtype=col_data.get("dtype", "any"),
            required=col_data.get("required", True),
            min=col_data.get("min"),
            max=col_data.get("max"),
            max_missing_pct=col_data.get("max_missing_pct"),
            allowed_values=allowed,
        )

    return SchemaContract(
        version=str(data.get("version", "1.0")),
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
        global_rules=global_rules,
        columns=columns,
    )
