from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from emd.cli._app import schema_app
from emd.cli._pipeline import ensure_file, load_or_exit
from emd.cli._ui import (
    SEVERITY_COLORS,
    console,
    err_console,
    header,
    make_table,
    output_panel,
    status,
)


@schema_app.command("init")
def schema_init(
    file: Annotated[Path, typer.Argument(help="CSV or XLSX file to generate schema from")],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output path for schema YAML")
    ] = None,
    name: Annotated[str, typer.Option("--name", help="Human-readable dataset name")] = "",
    sheet: Annotated[str | None, typer.Option("--sheet", help="XLSX sheet name")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output")] = False,
) -> None:
    """Generate a YAML schema contract from a data file."""
    ensure_file(file)

    from emd.schema.contract import save_contract
    from emd.schema.generator import ContractGenerator

    if not quiet:
        header("schema init", file.name)

    with status("Loading data...", quiet):
        df = load_or_exit(file, sheet)
        contract_name = name or file.stem
        contract = ContractGenerator.from_dataframe(df, name=contract_name)
        out_path = output or (file.parent / "schemas" / f"{file.stem}_schema.yaml")
        save_contract(contract, out_path)

    if not quiet:
        console.print()
        table = make_table("Column", "Dtype", "Required", "Missing <=", "Range / Values")
        for col, rule in contract.columns.items():
            missing_str = f"{rule.max_missing_pct}%" if rule.max_missing_pct is not None else "—"
            if rule.dtype == "numeric":
                range_str = f"[{rule.min}, {rule.max}]" if rule.min is not None else "—"
            elif rule.allowed_values is not None:
                vals = rule.allowed_values[:5]
                range_str = str(vals) + ("…" if len(rule.allowed_values) > 5 else "")
            else:
                range_str = "—"
            table.add_row(col, rule.dtype, str(rule.required), missing_str, range_str)
        console.print(table)
        console.print()
        min_rows = contract.global_rules.min_rows
        col_detail = f"{len(contract.columns)}  [dim](min_rows={min_rows})[/dim]"
        output_panel({"Schema": str(out_path), "Columns": col_detail})


@schema_app.command("validate")
def schema_validate(
    file: Annotated[Path, typer.Argument(help="CSV or XLSX file to validate")],
    schema: Annotated[Path, typer.Option("--schema", "-s", help="Path to schema YAML contract")],
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output")] = False,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
    sheet: Annotated[str | None, typer.Option("--sheet", help="XLSX sheet name")] = None,
) -> None:
    """Validate a data file against a YAML schema contract. Exits 0 on pass, 1 on fail."""
    ensure_file(file)
    if not schema.exists():
        err_console.print(f"[red]Schema not found:[/red] {schema}")
        raise typer.Exit(1)

    from emd.schema.contract import load_contract
    from emd.schema.validator import SchemaValidator

    if not quiet:
        header("schema validate", f"{file.name} -> {schema.name}")

    with status("Loading data...", quiet):
        df = load_or_exit(file, sheet)
        contract = load_contract(schema)
        result = SchemaValidator.validate(df, contract, strict=strict)

    if not quiet:
        console.print()
        if result.violations:
            table = make_table("Column", "Check", "Expected", "Actual", "Severity")
            for v in result.violations:
                color = SEVERITY_COLORS.get(v.severity, "white")
                sev_cell = f"[{color}]{v.severity}[/{color}]"
                table.add_row(v.column, v.check, v.expected, v.actual, sev_cell)
            console.print(table)
            console.print()
        if result.passed:
            console.print(
                f"[bold green]PASSED[/bold green] — {len(result.violations)} warning(s)\n"
            )
        else:
            error_count = sum(1 for v in result.violations if v.severity == "error")
            warning_count = sum(1 for v in result.violations if v.severity == "warning")
            console.print(
                f"[bold red]FAILED[/bold red] — {error_count} error(s), "
                f"{warning_count} warning(s)\n"
            )
    elif not result.passed:
        error_count = sum(1 for v in result.violations if v.severity == "error")
        warning_count = sum(1 for v in result.violations if v.severity == "warning")
        err_console.print(f"Validation failed: {error_count} error(s), {warning_count} warning(s)")

    raise typer.Exit(0 if result.passed else 1)
