# Statistical Methods & Assumption Transparency

This document describes every statistical test and metric computed by `emd`, the assumptions each method relies on, and how `emd` detects and reports when those assumptions are violated.

The goal is full transparency: every method is applied, but the report tells you when to trust the result and when to interpret it with caution.

---

## 1. Distribution Analysis

### Numeric columns

| Metric | Formula / Method | Notes |
|:-------|:----------------|:------|
| Mean | arithmetic mean | Sensitive to outliers and skewness |
| Median | 50th percentile | Robust to outliers |
| Mode | most frequent value | First mode if multimodal |
| Std | sample standard deviation (ddof=1) | Bessel's correction applied |
| Variance | std² | Sample variance |
| CV | std / \|mean\| | Coefficient of variation; only meaningful for ratio-scale data |
| Percentiles | p5, p25, p50, p75, p95 | Linear interpolation (numpy default) |
| IQR | p75 − p25 | Non-parametric spread measure |
| Skewness | Fisher-Pearson moment coefficient | `scipy.stats.skew` |
| Excess kurtosis | Fisher's definition (normal = 0) | `scipy.stats.kurtosis` |
| Normality test | Shapiro-Wilk (n ≤ 5000) or D'Agostino-Pearson (n > 5000) | See assumption notes below |
| Unique % | unique values / n | High value may indicate an ID column |

### Categorical columns

| Metric | Formula / Method | Notes |
|:-------|:----------------|:------|
| Mode | most frequent category | |
| Mode frequency | count of modal value | |
| Shannon entropy | −Σ p·log₂(p), normalized to [0, 1] | 0 = constant, 1 = uniform distribution |
| Top values | up to 10 most frequent values with count and % | |

### Assumption notes reported in the output

`emd` checks the following and adds a `> Note:` callout in the report when a condition is met:

| Condition | Threshold | What the note says |
|:----------|:----------|:-------------------|
| Moderate skewness | \|skew\| > 1.0 | Mean may overstate the typical value; report median alongside |
| Heavy skewness | \|skew\| > 2.0 | Mean is substantially pulled toward the tail; prefer median and IQR |
| Large-sample normality inflation | n > 2,000 and p < 0.05 | The normality test has very high power at large n — even trivially small deviations produce significant p-values. Use skewness and kurtosis to judge practical normality |
| Negative mean | mean < 0 | CV = std / \|mean\|; CV is most meaningful for strictly positive ratio-scale variables |
| Zero variance | std = 0 | All values are identical; correlations and most statistics are undefined |
| Unique ratio ≈ 1.0 | unique / n > 0.95 and n ≥ 50 | Likely an ID or free-text column, not a true feature |
| High cardinality (categorical) | unique > 50 | Chi-squared and Cramér's V lose statistical power |
| Small categorical sample | n < 30 | Frequency estimates and entropy are unreliable |

---

## 2. Correlation Analysis

### Methods applied

| Method | What it measures | Assumptions |
|:-------|:----------------|:-----------|
| **Pearson r** | Linear association between two numeric variables | Bivariate normality, linearity, no extreme outliers |
| **Spearman ρ** | Monotonic association (rank-based) | No distributional assumptions; robust to outliers and skewness |
| **Cramér's V** | Association between two categorical variables | Based on chi-squared; requires sufficient expected cell counts |
| **Point-biserial r** | Association between a numeric and a binary variable | Mathematically equivalent to Pearson r with a 0/1 variable |
| **VIF** | Variance Inflation Factor — multicollinearity severity | Requires an intercept in the regression model (applied correctly here) |

Both Pearson and Spearman matrices are always computed when ≥ 2 numeric columns are present. The report shows both heatmaps so the reader can compare.

**Why both?** If Pearson and Spearman agree closely, the relationship is likely linear and normally distributed. If they diverge substantially, the relationship is non-linear, skewed, or outlier-driven — and Spearman is the more reliable measure.

### VIF implementation note

VIF is computed by regressing each variable against all others with an intercept column included. Without the intercept, `statsmodels.variance_inflation_factor` computes uncentered R², which can produce VIF < 1 or negative values for non-zero-mean variables — a well-known pitfall. `emd` adds the intercept column explicitly before passing the matrix.

### Assumption notes reported in the output

| Condition | Threshold | What the note says |
|:----------|:----------|:-------------------|
| Pearson vs Spearman gap | \|r_P − ρ_S\| > 0.15 and \|ρ_S\| > 0.2 | Non-linear relationship or outlier influence suspected; Spearman is more reliable |
| Moderate multicollinearity | VIF > 5 | Monitor this variable if using linear regression |
| Severe multicollinearity | VIF > 10 | OLS coefficient estimates will be unstable; consider removing or regularising |
| High-cardinality categorical | unique > 20 | Chi-squared (and Cramér's V) loses power; interpret with caution |
| Multiple skewed numeric columns | ≥ 2 columns with \|skew\| > 2.0 | Pearson may understate true associations; refer to Spearman heatmap |

---

## 3. Missing Value Analysis

| Metric | Description |
|:-------|:------------|
| Per-column missing count and % | Direct count of NaN values |
| Global missing % | total missing cells / total cells |
| Complete rows | rows with no missing value in any column |
| Missingness patterns | unique combinations of which columns are simultaneously missing, ranked by frequency |
| Correlated missingness | P(col_A missing AND col_B missing in the same row) — pairs above 0.5 are reported |

No assumption violations are reported here — missingness counts are non-parametric observations, not statistical estimates.

---

## 4. Outlier Detection

Three methods are always applied. A fourth (Isolation Forest) is optional.

### Methods

**IQR (Tukey fences)**
- Standard fence: x < Q1 − 1.5·IQR or x > Q3 + 1.5·IQR
- Extreme fence: 3.0·IQR multiplier
- Assumption: works best for roughly symmetric distributions
- For skewed data: the upper fence will be crossed more often by legitimate tail values

**Z-score**
- Flag if |z| > 3, where z = (x − mean) / std (ddof=1)
- Assumption: **requires approximate normality**
- For skewed or heavy-tailed data: inflates the outlier count because mean and std are themselves distorted by the tail

**Modified Z-score (Iglewicz & Hoaglin, 1993)**
- Score = 0.6745 · (x − median) / MAD, flag if |score| > 3.5
- The constant 0.6745 = Φ⁻¹(0.75) — the 75th percentile of the standard normal, making the score consistent with a normal-distribution reference
- MAD (Median Absolute Deviation) is robust to outliers and does not assume normality
- **Preferred method for non-normal and skewed distributions**

**Isolation Forest** (optional, requires scikit-learn)
- Tree-based anomaly detection; no distributional assumptions
- Contamination is set automatically unless overridden

### Assumption notes reported in the output

| Condition | Threshold | What the note says |
|:----------|:----------|:-------------------|
| Z-score on skewed data | \|skew\| > 1.5 | Z-score may inflate the outlier count; prefer Modified Z-score |
| Z-score >> Modified Z-score | zscore > 3× mzscore | Methods disagree substantially; prefer Modified Z-score for non-symmetric data |
| Modified Z-score >> Z-score | zscore = 0 and mzscore > 0 | Modified Z-score catches asymmetric outliers that Z-score misses |
| IQR on heavily skewed data | \|skew\| > 2.0 and IQR count > 0 | Some flagged values may be legitimate tail observations |
| MAD = 0 | majority of values identical | Modified Z-score is undefined; inspect the value distribution directly |

---

## 5. Target Variable Analysis (`--target`)

Ranks all other columns by their statistical association with the chosen target. The method used depends on the variable types involved.

| Feature type | Target type | Method | Assumption |
|:-------------|:------------|:-------|:-----------|
| Numeric | Numeric | Pearson r | Bivariate normality, linearity |
| Numeric | Binary categorical | Point-biserial r | Equal to Pearson r with 0/1 encoding |
| Numeric | Multi-class categorical | Eta-squared from one-way ANOVA | Equal group variances (Levene), normal residuals within groups |
| Binary categorical | Numeric | Point-biserial r | — |
| Categorical | Categorical | Cramér's V | Sufficient expected cell counts |

### Eta-squared formula

η² = F·(k−1) / [F·(k−1) + (n−k)]

where k = number of groups, n = total observations. This is an exact algebraic derivation from the F-statistic — not an approximation.

### Assumption notes reported in the output

| Condition | Threshold | What the note says |
|:----------|:----------|:-------------------|
| Levene's test rejected | p < 0.05 per column | ANOVA / eta-squared assumes equal group variances; scores for these columns may be inflated; consider Welch's ANOVA or Kruskal-Wallis |
| Small group size | n < 30 per class | Correlation estimates are unstable; point-biserial and eta-squared require n ≥ 30 per group for reliable inference |
| Skewed numeric target | \|skew\| > 2.0 | Pearson r assumes bivariate normality; associations may be understated; consider log-transforming the target before modelling |

---

## 6. Data Drift Detection (`emd compare`)

### Methods

**PSI — Population Stability Index** (numeric columns)

PSI = Σ (p_current − p_reference) · ln(p_current / p_reference)

Bins are determined by reference-data quantiles (equal-frequency binning with 10 bins). This ensures the reference distribution is uniformly spread across bins, making PSI sensitive to shifts in any part of the distribution.

| PSI value | Severity | Interpretation |
|:----------|:---------|:---------------|
| < 0.1 | None | Distributions are stable |
| 0.1 – 0.2 | Moderate | Minor shift; monitor |
| ≥ 0.2 (default threshold) | High | Significant drift detected |

The threshold can be changed with `--threshold`.

**KS test — Kolmogorov-Smirnov** (numeric columns)

Two-sample KS test (`scipy.stats.ks_2samp`). Reports the test statistic (maximum absolute difference between empirical CDFs) and the p-value. A significant p-value (< 0.05) indicates the two samples are unlikely to come from the same distribution.

**Chi-squared test** (categorical columns)

A 2 × k contingency table is constructed (reference vs current, across k categories). `scipy.stats.chi2_contingency` tests whether category proportions differ between the two datasets. p < 0.05 flags drift for that column.

### Drift verdict logic

- A column is flagged as **drifted** if PSI ≥ threshold (numeric) or chi-squared p < 0.05 (categorical)
- `overall_drift` is set to `True` if any column is drifted
- The report prints `DATA DRIFT DETECTED` with the list of affected columns

---

## Design principle

`emd` applies all methods to every dataset by default. This is intentional: the goal of EDA is exploration, and skipping a test because the data "probably" doesn't meet its assumptions removes information the analyst should have.

Instead, `emd` flags assumption violations in the report with `> Note:` callouts — directly beneath the affected metric. The analyst sees both the result and its reliability assessment together, and can decide how much weight to give each number.

This is different from hiding results behind gate conditions. A Pearson r of 0.6 on skewed data is still a data point — the note simply adds context: "Spearman gives 0.8; the relationship is non-linear and Pearson understates it."
