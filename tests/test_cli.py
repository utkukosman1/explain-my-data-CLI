"""Smoke tests for every CLI command: exit codes, files on disk, key output."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from emd.cli import app

runner = CliRunner()


@pytest.fixture
def small_csv(tmp_path: Path) -> Path:
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "num_a": rng.normal(10, 2, 60),
        "num_b": rng.uniform(0, 5, 60),
        "cat": rng.choice(["x", "y", "z"], 60),
    })
    path = tmp_path / "small.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def small_xlsx(tmp_path: Path) -> Path:
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    path = tmp_path / "small.xlsx"
    df.to_excel(path, index=False, sheet_name="First")
    return path


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "emd version" in result.output


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.output


def test_info() -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "pandas" in result.output


def test_check(small_csv: Path) -> None:
    result = runner.invoke(app, ["check", str(small_csv)])
    assert result.exit_code == 0
    assert "Quality gate" in result.output


def test_summary(small_csv: Path) -> None:
    result = runner.invoke(app, ["summary", str(small_csv)])
    assert result.exit_code == 0
    assert "Key Issues" in result.output
    assert "At a Glance" in result.output


def test_summary_missing_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["summary", str(tmp_path / "nope.csv")])
    assert result.exit_code == 1


def test_summary_bad_target(small_csv: Path) -> None:
    result = runner.invoke(app, ["summary", str(small_csv), "--target", "not_a_column"])
    assert result.exit_code == 1


def test_doctor(small_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["doctor", str(small_csv), "-o", str(out)])
    assert result.exit_code == 0
    assert "Dataset Health Score" in result.output
    report = out / "small" / "doctor-report.md"
    assert report.exists()
    assert "## 1. Dataset Health Score" in report.read_text(encoding="utf-8")


def test_doctor_with_target(small_csv: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["doctor", str(small_csv), "-o", str(tmp_path / "out"), "--target", "num_a"],
    )
    assert result.exit_code == 0


def test_doctor_quiet_still_writes_report(small_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["doctor", str(small_csv), "-o", str(out), "--quiet"])
    assert result.exit_code == 0
    assert (out / "small" / "doctor-report.md").exists()


def test_analyze(small_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["analyze", str(small_csv), "-o", str(out)])
    assert result.exit_code == 0
    report_dir = out / "small"
    assert (report_dir / "report.md").exists()
    charts = list((report_dir / "charts").glob("*.png"))
    assert charts, "expected at least one chart file"


def test_analyze_quiet_json_stdout(small_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(
        app, ["analyze", str(small_csv), "-o", str(out), "--quiet", "--output-json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {"quality", "distribution", "missing"} <= set(payload.keys())


def test_analyze_missing_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["analyze", str(tmp_path / "nope.csv")])
    assert result.exit_code == 1


def test_batch(small_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["batch", str(small_csv.parent), "-o", str(out), "--quiet"])
    assert result.exit_code == 0
    assert (out / "small" / "report.md").exists()


def test_batch_not_a_directory(small_csv: Path) -> None:
    result = runner.invoke(app, ["batch", str(small_csv)])
    assert result.exit_code == 1


def test_compare(small_csv: Path, tmp_path: Path) -> None:
    other = tmp_path / "other.csv"
    other.write_text(small_csv.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "out"
    result = runner.invoke(app, ["compare", str(small_csv), str(other), "-o", str(out)])
    assert result.exit_code == 0
    assert (out / "small_vs_other" / "drift_report.md").exists()


def test_sheets(small_xlsx: Path) -> None:
    result = runner.invoke(app, ["sheets", str(small_xlsx)])
    assert result.exit_code == 0
    assert "First" in result.output


def test_sheets_rejects_csv(small_csv: Path) -> None:
    result = runner.invoke(app, ["sheets", str(small_csv)])
    assert result.exit_code == 1


def test_schema_init_and_validate(small_csv: Path, tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    result = runner.invoke(app, ["schema", "init", str(small_csv), "-o", str(schema_path)])
    assert result.exit_code == 0
    assert schema_path.exists()

    result = runner.invoke(
        app, ["schema", "validate", str(small_csv), "--schema", str(schema_path)],
    )
    assert result.exit_code == 0
    assert "PASSED" in result.output


def test_schema_validate_fails_on_broken_data(small_csv: Path, tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    runner.invoke(app, ["schema", "init", str(small_csv), "-o", str(schema_path)])

    broken = tmp_path / "broken.csv"
    df = pd.read_csv(small_csv).drop(columns=["num_b"])
    df.to_csv(broken, index=False)

    result = runner.invoke(app, ["schema", "validate", str(broken), "--schema", str(schema_path)])
    assert result.exit_code == 1
    assert "FAILED" in result.output
