# CLI Reference

All commands are available after `pip install -e .` via the `emd` entry point.

---

## emd analyze

Runs the full EDA pipeline on a single CSV or XLSX file and produces a Markdown report with embedded charts.

```bash
emd analyze <file> [OPTIONS]
```

**What it does — in order:**
1. Loads the file (auto-detects encoding and delimiter for CSV)
2. Runs the data quality gate — aborts on FATAL issues, logs warnings otherwise
3. Runs all analysis modules: distribution, correlation, missing values, outlier detection
4. If `--target` is provided, runs target variable analysis
5. Renders all charts as PNG files into `<output>/<filename>/charts/`
6. Writes `<output>/<filename>/report.md`
7. If `--output-json` is set, also writes `analysis_results.json`

**Options:**

| Option | Default | Description |
|:-------|:--------|:------------|
| `--output`, `-o` | `./reports` | Output directory |
| `--target` | — | Column name to use as target variable (adds Key Insights section) |
| `--chart-format` | `png` | Chart format: `png` or `svg` |
| `--theme` | `light` | Chart theme: `light` or `dark` |
| `--sheet` | — | Sheet name for XLSX files |
| `--parse-dates` | — | Comma-separated column names to parse as dates |
| `--drop-cols` | — | Comma-separated columns to exclude before analysis |
| `--sample` | — | Analyze a random sample of N rows |
| `--skip-correlation` | off | Skip correlation analysis (faster run) |
| `--skip-outlier` | off | Skip outlier detection |
| `--use-iforest` | off | Add Isolation Forest to outlier methods (requires scikit-learn) |
| `--output-json` | off | Also write `analysis_results.json` |
| `--quiet`, `-q` | off | Suppress progress output (prints JSON to stdout if `--output-json`) |
| `--no-quality-gate` | off | Continue even if quality gate returns FATAL |

**Examples:**

```bash
emd analyze data.csv
emd analyze data.csv --target SalePrice --output ./reports
emd analyze data.xlsx --sheet "Q1 Results" --theme dark
emd analyze big_file.csv --sample 10000 --skip-correlation
emd analyze data.csv --output-json --quiet   # JSON to stdout for scripting
```

---

## emd summary

Prints a fast terminal recap of a dataset — a ranked list of Key Issues plus an At a Glance table. Nothing is written to disk: no charts, no `report.md`, no JSON. It runs the same analyzers as `emd analyze` but skips chart rendering and report generation, making it the quickest way to get oriented on a new file before committing to a full report.

```bash
emd summary <file> [OPTIONS]
```

**What it does — in order:**
1. Loads the file (auto-detects encoding and delimiter for CSV)
2. Runs the data quality gate — aborts on FATAL issues, logs warnings otherwise
3. Runs distribution, missing value, correlation, and outlier analysis
4. Prints **Key Issues**: up to 5 findings, prioritized by severity (constant/zero-variance columns, then duplicate rows, high missingness, severe multicollinearity, strong correlations, identifier-like columns, heavy skew, and outlier concentration). Prints "No significant issues detected." if nothing qualifies.
5. Prints **At a Glance**: row/column counts, missing %, duplicate row count, numeric/categorical feature counts, and the target column if `--target` was given

**Options:**

| Option | Default | Description |
|:-------|:--------|:------------|
| `--target` | — | Column name to show in the At a Glance table |
| `--sheet` | — | Sheet name for XLSX files |
| `--parse-dates` | — | Comma-separated column names to parse as dates |
| `--drop-cols` | — | Comma-separated columns to exclude before analysis |
| `--sample` | — | Analyze a random sample of N rows |
| `--skip-correlation` | off | Skip correlation analysis (faster run) |
| `--skip-outlier` | off | Skip outlier detection |
| `--no-quality-gate` | off | Continue even if quality gate returns FATAL |

**Examples:**

```bash
emd summary data.csv
emd summary data.csv --target SalePrice
emd summary big_file.csv --sample 10000
```

---

## emd compare

Compares two datasets for statistical distribution shift (data drift). Useful for MLOps pipelines, monitoring production data, or comparing train/test splits.

```bash
emd compare <reference> <current> [OPTIONS]
```

**What it does:**
1. Loads both files
2. Identifies shared columns, columns missing in current, and new columns in current
3. For each shared numeric column: computes PSI, KS test, mean shift
4. For each shared categorical column: computes chi-squared test
5. Flags columns where drift is detected
6. Renders overlay histograms for drifted columns and a PSI summary chart
7. Writes `<output>/<ref>_vs_<cur>/drift_report.md`

**Options:**

| Option | Default | Description |
|:-------|:--------|:------------|
| `--output`, `-o` | `./reports` | Output directory |
| `--threshold` | `0.2` | PSI threshold above which drift is flagged as "high" |
| `--quiet`, `-q` | off | Suppress progress output |

**Examples:**

```bash
emd compare train.csv test.csv
emd compare january.csv february.csv --output ./drift_reports
emd compare train.csv production.csv --threshold 0.15
```

---

## emd check

Runs only the data quality gate on a file — no analysis, no report. Useful for quick sanity checks.

```bash
emd check <file> [OPTIONS]
```

**What it checks:**

| Check | Severity | Action |
|:------|:---------|:-------|
| 0 rows or 0 columns | FATAL | Would abort the pipeline |
| Column with > 90% missing values | WARNING | Flagged, analysis would continue |
| > 50% duplicate rows | WARNING | Flagged |
| All columns are `object` dtype | WARNING | Likely a parsing failure |
| Special characters in column names | INFO | Noted |
| Mixed types in a column | WARNING | Flagged with affected column name |

**Options:**

| Option | Default | Description |
|:-------|:--------|:------------|
| `--sheet` | — | Sheet name for XLSX files |

**Example:**

```bash
emd check data.csv
emd check data.xlsx --sheet "Raw Data"
```

---

## emd batch

Runs `emd analyze` on every CSV and XLSX file found in a directory.

```bash
emd batch <directory> [OPTIONS]
```

**Options:**

| Option | Default | Description |
|:-------|:--------|:------------|
| `--output`, `-o` | `./reports` | Output directory (each file gets its own subfolder) |
| `--quiet`, `-q` | off | Suppress per-file progress output |

**Example:**

```bash
emd batch ./data/
emd batch ./datasets/ --output ./all_reports --quiet
```

---

## emd sheets

Lists all sheet names in an Excel file. Helpful before using `--sheet`.

```bash
emd sheets <file>
```

**Example:**

```bash
emd sheets workbook.xlsx
```

---

## emd schema init

Reads a data file and generates a YAML schema contract that captures the current dataset's structure as a reusable quality standard. Run this once on a known-good dataset; commit the YAML; validate every future delivery against it.

```bash
emd schema init <file> [OPTIONS]
```

**What it captures per column:**

| Column type | Fields written |
|:------------|:---------------|
| Numeric | `dtype`, `min` (actual − 10%), `max` (actual + 10%), `max_missing_pct` |
| Categorical (≤ 20 unique values) | `dtype`, `allowed_values`, `max_missing_pct` |
| Categorical (> 20 unique values) | `dtype`, `max_missing_pct` |
| Datetime | `dtype`, `max_missing_pct` |

The 10% buffer on numeric bounds and 1.5× buffer on missing percentages give real pipelines room to breathe while still catching meaningful deviations. A column with 0% missing stays at 0% — no buffer applied.

**Global rules written:**

| Rule | Value |
|:-----|:------|
| `min_rows` | 80% of current row count |
| `max_duplicate_pct` | current duplicate % × 1.5 + 1.0 |
| `extra_columns` | `warn` (extra columns in future data trigger a warning, not a failure) |

**Options:**

| Option | Default | Description |
|:-------|:--------|:------------|
| `--output`, `-o` | `<file_dir>/schemas/<filename>_schema.yaml` | Output path for the YAML contract |
| `--name` | filename stem | Human-readable dataset name written into the contract |
| `--sheet` | — | Sheet name for XLSX files |
| `--quiet`, `-q` | off | Suppress the column summary table |

**Examples:**

```bash
emd schema init sales.csv
emd schema init sales.csv --output contracts/sales_schema.yaml --name "Monthly Sales"
emd schema init data.xlsx --sheet "Raw" --quiet
```

**Example output (`sales_schema.yaml`):**

```yaml
version: '1.0'
name: Monthly Sales
description: ''
global:
  extra_columns: warn
  min_rows: 800
  max_duplicate_pct: 1.0
columns:
  age:
    dtype: numeric
    required: true
    min: 17.1
    max: 71.5
    max_missing_pct: 0.0
  category:
    dtype: categorical
    required: true
    max_missing_pct: 0.0
    allowed_values:
    - A
    - B
    - C
```

---

## emd schema validate

Validates a data file against a previously generated YAML schema contract. Designed for CI/CD pipelines — exits 0 on pass, 1 on failure.

```bash
emd schema validate <file> --schema <schema.yaml> [OPTIONS]
```

**Checks performed, in order:**

1. **Global: row count** — fails if `len(df) < min_rows`
2. **Global: duplicate rows** — fails if duplicate percentage exceeds `max_duplicate_pct`
3. **Required columns** — fails for each column marked `required: true` that is absent
4. **Extra columns** — warns (or fails if `extra_columns: fail`) for columns not in the contract
5. **Per-column dtype** — fails if the actual dtype doesn't match; skips further checks for that column
6. **Per-column missing %** — fails if `null %` exceeds `max_missing_pct`
7. **Numeric bounds** — fails if any value is below `min` or above `max`
8. **Categorical values** — warns if values outside `allowed_values` are found

Warnings do not cause a failure by default. Use `--strict` to promote all warnings to errors.

**Options:**

| Option | Default | Description |
|:-------|:--------|:------------|
| `--schema`, `-s` | *(required)* | Path to the YAML schema contract |
| `--strict` | off | Treat warnings as errors (exit 1 if any warning fires) |
| `--quiet`, `-q` | off | No output on pass; only violation count on fail (pure exit-code mode) |
| `--sheet` | — | Sheet name for XLSX files |

**Exit codes:**

| Code | Meaning |
|:-----|:--------|
| `0` | All checks passed (warnings may exist unless `--strict`) |
| `1` | One or more errors (or warnings with `--strict`) |

**Examples:**

```bash
# Basic validation
emd schema validate sales_feb.csv --schema sales_schema.yaml

# Strict mode — warnings also block the pipeline
emd schema validate sales_feb.csv --schema sales_schema.yaml --strict

# Silent mode for CI/CD — no output on success, violation count on failure
emd schema validate sales_feb.csv --schema sales_schema.yaml --quiet
echo "Exit code: $?"
```

**CI/CD integration examples:**

```yaml
# GitHub Actions step
- name: Validate incoming data
  run: emd schema validate data/latest.csv --schema contracts/schema.yaml --quiet

# Airflow BashOperator
BashOperator(
    task_id="validate_data",
    bash_command="emd schema validate {{ params.file }} --schema {{ params.schema }} --quiet",
)
```

**Example output (with violations):**

```
Validation: sales_feb.csv  ->  schema: sales_schema.yaml

┌────────────┬─────────────────┬─────────────────────┬─────────────────┬──────────┐
│ Column     │ Check           │ Expected             │ Actual           │ Severity │
├────────────┼─────────────────┼─────────────────────┼──────────────────┼──────────┤
│ __global__ │ min_rows        │ >= 800               │ 650              │ error    │
│ category   │ allowed_values  │ subset of ['A', 'B', │ unexpected:      │ warning  │
│            │                 │ 'C']                 │ ['D']            │          │
│ income     │ max_missing_pct │ <= 0.0%              │ 14.2%            │ error    │
└────────────┴─────────────────┴─────────────────────┴──────────────────┴──────────┘

FAILED — 2 error(s), 1 warning(s)
```

The table is rendered by [Rich](https://github.com/Textualize/rich) and wraps wide cells (like long `allowed_values` lists) onto multiple lines rather than truncating — the exact column widths depend on your terminal width.

---

## emd info

Shows the installed version of `emd` and the status of all dependencies, including optional ones.

```bash
emd info
```

Output includes each package name, installed version, and whether it is present. Useful for verifying that optional dependencies (e.g. `scikit-learn` for Isolation Forest) are available.

---

## Output structure

Every `emd analyze` run produces:

```
<output>/<filename>/
  report.md              # full Markdown report
  analysis_results.json  # (only with --output-json)
  charts/
    distribution_<col>.png
    categorical_<col>.png
    correlation_pearson.png
    correlation_spearman.png
    correlation_top_pairs.png
    missing_bar.png
    outlier_<col>.png
    outlier_comparison.png
    target_hist_<col>.png    # (only with --target, categorical target)
    target_scatter_<col>.png # (only with --target, numeric target)
```

Every `emd compare` run produces:

```
<output>/<ref>_vs_<cur>/
  drift_report.md
  charts/
    drift_<col>.png       # overlay histogram per drifted column
    drift_psi_summary.png # PSI bar chart with threshold line
```
