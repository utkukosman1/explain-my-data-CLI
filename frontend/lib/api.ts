const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface AnalyzeOptions {
  skipCorrelation?: boolean;
  skipOutlier?: boolean;
  useIforest?: boolean;
  target?: string;
  dropCols?: string;
  sampleSize?: number;
}

export interface JobCreated {
  job_id: string;
  status: string;
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "done" | "failed";
  progress: number;
  step: string;
  result: AnalysisResult | null;
  error: string | null;
}

// ---- Result types ----

export interface AnalysisResult {
  overview: Overview;
  quality: Quality;
  distribution: Distribution;
  missing: Missing;
  correlation: Correlation | null;
  outlier: Outlier | null;
  target: Target | null;
  _markdown?: string;
}

export interface Overview {
  filename: string;
  rows: number;
  cols: number;
  memory_kb: number;
  columns: ColumnMeta[];
}

export interface ColumnMeta {
  name: string;
  dtype: string;
  non_null: number;
  null_pct: number;
}

export interface Quality {
  issues: QualityIssue[];
  passed: boolean;
  has_warnings: boolean;
}

export interface QualityIssue {
  check: string;
  severity: "FATAL" | "WARNING" | "INFO";
  result: string;
  recommendation: string;
}

export interface Distribution {
  numeric: NumericCol[];
  categorical: CategoricalCol[];
}

export interface NumericCol {
  name: string;
  count: number;
  null_pct: number;
  mean: number | null;
  median: number | null;
  std: number | null;
  skewness: number | null;
  excess_kurtosis: number | null;
  min: number | null;
  max: number | null;
  p25: number | null;
  p75: number | null;
  assumptions: string[];
  chart_data: HistBin[];
  box_data: BoxData;
}

export interface HistBin {
  bin: string;
  x: number;
  x1: number;
  count: number;
}

export interface BoxData {
  min: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  max: number | null;
  mean: number | null;
}

export interface CategoricalCol {
  name: string;
  count: number;
  null_pct: number;
  unique_count: number;
  entropy: number;
  chart_data: CatBar[];
  assumptions: string[];
}

export interface CatBar {
  value: string;
  count: number;
  pct: number;
}

export interface Missing {
  global_missing_pct: number;
  total_missing: number;
  total_cells: number;
  complete_rows: number;
  complete_rows_pct: number;
  chart_data: MissingBar[];
  columns: MissingCol[];
}

export interface MissingBar {
  column: string;
  missing_pct: number;
  missing_count: number;
}

export interface MissingCol {
  name: string;
  missing_count: number;
  missing_pct: number;
}

export interface Correlation {
  pearson: CorrCell[] | null;
  pearson_columns: string[];
  spearman: CorrCell[] | null;
  spearman_columns: string[];
  strong_pairs: StrongPair[];
  vif: Record<string, number | null> | null;
  warnings: string[];
}

export interface CorrCell {
  row: string;
  col: string;
  value: number | null;
}

export interface StrongPair {
  col_a: string;
  col_b: string;
  r: number;
  label: string;
}

export interface Outlier {
  methods_used: string[];
  chart_data: OutlierBar[];
  columns: OutlierCol[];
}

export interface OutlierBar {
  column: string;
  IQR: number;
  IQR_extreme: number;
  Z_score: number;
  Modified_Z: number;
}

export interface OutlierCol {
  name: string;
  iqr_count: number;
  iqr_pct: number;
  zscore_count: number;
  mzscore_count: number;
}

export interface Target {
  target_col: string;
  target_type: string;
  top_features: TargetFeature[];
  all_features: TargetFeature[];
  warnings: string[];
}

export interface TargetFeature {
  feature: string;
  score: number;
  method: string;
  direction: string;
}

// ---- Drift / Compare types ----

export interface DriftResult {
  ref_name: string;
  cur_name: string;
  summary: DriftSummary;
  columns: DriftColumn[];
  drifted_columns: string[];
  chart_data: Record<string, DriftOverlayBin[]>;
}

export interface DriftSummary {
  reference_shape: [number, number];
  current_shape: [number, number];
  drifted_count: number;
  total_columns: number;
  drift_fraction: number;
  overall_drift: boolean;
  missing_in_current: string[];
  new_in_current: string[];
  psi_threshold: number;
}

export interface DriftColumn {
  name: string;
  col_type: string;
  psi: number | null;
  ks_pvalue: number | null;
  mean_shift_pct: number | null;
  chi2_pvalue: number | null;
  drift_detected: boolean;
  drift_severity: "none" | "moderate" | "high";
  mean_ref: number | null;
  mean_cur: number | null;
}

export interface DriftOverlayBin {
  bin: string;
  x: number;
  reference: number;
  current: number;
}

// ---- API functions ----

export async function uploadAndAnalyze(
  file: File,
  options: AnalyzeOptions = {}
): Promise<JobCreated> {
  const form = new FormData();
  form.append("file", file);
  form.append("skip_correlation", String(options.skipCorrelation ?? false));
  form.append("skip_outlier", String(options.skipOutlier ?? false));
  form.append("use_iforest", String(options.useIforest ?? false));
  form.append("target", options.target ?? "");
  form.append("drop_cols", options.dropCols ?? "");
  form.append("sample_size", String(options.sampleSize ?? 0));

  const res = await fetch(`${BASE}/api/jobs/analyze`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${BASE}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Job not found: ${jobId}`);
  return res.json();
}

export function createJobSocket(jobId: string): WebSocket {
  const wsBase = BASE.replace(/^http/, "ws");
  return new WebSocket(`${wsBase}/api/ws/${jobId}`);
}

export async function uploadAndCompare(
  reference: File,
  current: File,
  threshold = 0.2
): Promise<JobCreated> {
  const form = new FormData();
  form.append("reference", reference);
  form.append("current", current);
  form.append("threshold", String(threshold));
  const res = await fetch(`${BASE}/api/jobs/compare`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Compare failed: ${res.statusText}`);
  return res.json();
}
