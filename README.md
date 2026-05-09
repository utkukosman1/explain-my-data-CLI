# Explain My Data CLI

Automated EDA reports from CSV/XLSX files — distributions, correlations, missing values, outlier detection, target variable analysis, and data drift detection, all in one Markdown report with charts.

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

Produces a `reports/<filename>/report.md` with embedded PNG charts.

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

### Target Variable Analysis

Add `--target` to focus the report on a specific column. Works with both numeric and categorical targets.

```bash
emd analyze titanic.csv --target Survived       # categorical target (binary)
emd analyze iris.csv --target species           # categorical target (multi-class)
emd analyze housing.csv --target SalePrice      # numeric target
```

When `--target` is set, the report gains a **Key Insights** section that shows:

- Top 5 features ranked by correlation with the target (Pearson r, point-biserial, Cramér's V, or eta-squared depending on column types)
- Hue-colored histograms and box plots split by target class (categorical target)
- Scatter plots of each top feature vs target value (numeric target)

### Data Drift Detection

Compare two datasets to detect statistical distribution shift — useful for MLOps pipelines, monitoring production data, or comparing train/test splits.

```bash
emd compare train.csv test.csv
emd compare january.csv february.csv --output ./drift_reports
emd compare train.csv test.csv --threshold 0.15   # custom PSI threshold (default: 0.2)
```

Produces a `drift_report.md` with:

- **PSI** (Population Stability Index) per numeric column — the MLOps standard drift metric
- **KS test** (Kolmogorov-Smirnov) p-value for distribution change
- **Mean shift %** per column
- **Chi-squared test** for categorical columns
- Overlay histograms (reference vs current) for every drifted column
- PSI summary bar chart with threshold line

Severity levels: `none` (PSI < 0.1) · `moderate` (0.1–0.2) · `high` (PSI ≥ 0.2 → drift detected)

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
| Key Insights (Target) | Top 5 correlated features, hue charts — only when `--target` is provided |
| Correlation Analysis | Pearson & Spearman heatmaps, Cramér's V (categorical), point-biserial, VIF, strongest pairs table |
| Missing Value Analysis | Per-column missing %, global stats, missingness patterns, correlated missingness pairs |
| Outlier Detection | IQR (1.5× and 3×), Z-score, Modified Z-score (MAD-based), optional Isolation Forest |
| Appendix | Full percentile table for all numeric columns |

## Project structure

```
src/emd/
  cli.py          — all commands (analyze, compare, check, batch, sheets, info)
  config.py       — ReportConfig dataclass
  loader/         — CSVLoader (auto-encoding, auto-delimiter) + XLSXLoader
  quality/        — QualityChecker
  analysis/       — distribution · correlation · missing · outlier · target · drift
  charts/         — ChartRenderer (matplotlib + seaborn)
  report/         — MarkdownReportGenerator + drift report + JSON output
datasets/         — 5 test datasets (titanic, iris, sp500, ames housing, airline passengers)
tests/            — 40 unit tests
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
