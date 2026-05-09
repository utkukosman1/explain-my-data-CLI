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
