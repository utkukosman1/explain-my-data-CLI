# Explain My Data CLI

Automated EDA reports from CSV/XLSX files — distributions, correlations, missing values, outlier detection, all in one Markdown report with charts.

## Installation

```bash
git clone https://github.com/utkukosman1/explain-my-data-CLI.git
cd explain-my-data-CLI
pip install -e .
```

For Isolation Forest outlier detection (optional):

```bash
pip install -e ".[ml]"
```

## Usage

### Full analysis

```bash
emd analyze data.csv
```

Produces a `reports/<filename>/report.md` with 87+ PNG charts embedded.

### Common options

```bash
emd analyze data.csv --output ./my_reports     # custom output directory
emd analyze data.csv --skip-correlation        # faster run, skip correlation
emd analyze data.csv --skip-outlier            # skip outlier detection
emd analyze data.csv --sample 5000             # analyze a random sample of N rows
emd analyze data.csv --theme dark              # dark chart theme
emd analyze data.csv --drop-cols col1,col2     # exclude columns before analysis
emd analyze data.xlsx --sheet "Sheet2"         # specific XLSX sheet
emd analyze data.csv --output-json --quiet     # output JSON to stdout (for scripting/UI)
emd analyze data.csv --use-iforest             # add Isolation Forest outlier method
```

### Other commands

```bash
emd check data.csv          # quality check only — no report generated
emd batch ./data/           # run analyze on every CSV/XLSX in a directory
emd sheets data.xlsx        # list sheet names in an Excel file
emd info                    # show version and dependency status
```

## What's in the report

| Section | What you get |
|:--------|:-------------|
| Data Quality Summary | FATAL/WARNING/INFO checks — empty data, high missing columns, duplicate rows, mixed types |
| Dataset Overview | Shape, dtypes, null counts, memory usage |
| Distribution Analysis | Mean, median, std, CV, skewness, kurtosis, normality test (Shapiro-Wilk / D'Agostino), percentiles, histogram + KDE, box plot |
| Correlation Analysis | Pearson & Spearman heatmaps, Cramér's V (categorical), point-biserial, VIF, strongest pairs table |
| Missing Value Analysis | Per-column missing %, global stats, missingness patterns, correlated missingness pairs |
| Outlier Detection | IQR (1.5× and 3×), Z-score, Modified Z-score (MAD-based), optional Isolation Forest |
| Appendix | Full percentile table for all numeric columns |

## Project structure

```
src/emd/
  cli.py          — all commands (analyze, check, batch, sheets, info)
  config.py       — ReportConfig dataclass
  loader/         — CSVLoader (auto-encoding, auto-delimiter) + XLSXLoader
  quality/        — QualityChecker
  analysis/       — distribution · correlation · missing · outlier
  charts/         — ChartRenderer (matplotlib + seaborn)
  report/         — MarkdownReportGenerator + JSON output
datasets/         — 5 test datasets (titanic, iris, sp500, ames housing, airline passengers)
tests/            — 25 unit tests
```

## JSON output (for scripting / UI integration)

```bash
emd analyze data.csv --output-json --quiet
```

Writes `analysis_results.json` alongside the Markdown report. The JSON schema is the stable API contract for downstream consumers (e.g. a TypeScript/React UI).

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/
```

## License

MIT
