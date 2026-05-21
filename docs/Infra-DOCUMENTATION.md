# Explain My Data — Documentation

> Full-stack automated EDA platform. Upload a CSV/Excel file, get instant statistical analysis with interactive charts. Supports drift detection, batch processing, and persistent dataset history.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Running Locally](#2-running-locally)
3. [Backend](#3-backend)
   - [Architecture](#31-architecture)
   - [Job Lifecycle](#32-job-lifecycle)
   - [API Reference](#33-api-reference)
   - [Analysis Service](#34-analysis-service)
   - [Serializer & Chart Data](#35-serializer--chart-data)
   - [JSON Response Schemas](#36-json-response-schemas)
4. [Frontend](#4-frontend)
   - [Architecture](#41-architecture)
   - [Pages & Routes](#42-pages--routes)
   - [Component Tree](#43-component-tree)
   - [Upload Flow](#44-upload-flow)
   - [Report Layout](#45-report-layout)
   - [Dataset History](#46-dataset-history)
   - [API Client](#47-api-client)
5. [Deployment](#5-deployment)
6. [Environment Variables](#6-environment-variables)

---

## 1. Project Structure

```
explain-my-data-CLI/
├── src/emd/                        # Python computation library (CLI)
│   ├── analysis/                   # Statistical analyzers
│   │   ├── distribution.py         # NumericColumnStats, CategoricalColumnStats
│   │   ├── correlation.py          # Pearson, Spearman, Cramér's V, VIF
│   │   ├── missing.py              # Missing value patterns
│   │   ├── outlier.py              # IQR, Z-score, MAD, Isolation Forest
│   │   ├── target.py               # Feature importance vs target
│   │   └── drift.py                # PSI, KS test, Chi-squared
│   ├── charts/renderer.py          # Matplotlib chart renderer (CLI only)
│   ├── quality/checker.py          # Data quality gates
│   ├── loader/                     # CSV / XLSX loaders
│   ├── report/generator.py         # Markdown + JSON report generator
│   └── cli.py                      # Typer CLI entry point
│
├── backend/                        # FastAPI web API
│   ├── main.py                     # App instance + CORS
│   ├── store.py                    # In-memory job store
│   ├── models/job.py               # Job dataclass + JobStatus enum
│   ├── routers/jobs.py             # All endpoints + WebSocket
│   ├── services/
│   │   ├── analysis_service.py     # Orchestrates emd modules
│   │   └── serializer.py           # JSON-safe + recharts data builders
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                       # Next.js 16 web app
│   ├── app/
│   │   ├── layout.tsx              # Root layout (AppShell wrapper)
│   │   ├── page.tsx                # Home dashboard
│   │   ├── analyze/page.tsx        # Upload + analyze flow
│   │   ├── compare/                # Drift compare flow
│   │   │   ├── page.tsx
│   │   │   └── result/[jobId]/page.tsx
│   │   ├── batch/page.tsx          # Batch analyze
│   │   └── report/[jobId]/page.tsx # Analysis results
│   ├── components/
│   │   ├── layout/AppShell.tsx     # Persistent sidebar
│   │   ├── upload/                 # UploadZone, AnalysisOptions, JobProgress
│   │   ├── compare/                # CompareUpload, DriftReport
│   │   ├── batch/BatchQueue.tsx    # Multi-file queue
│   │   └── report/                 # QualitySection, OverviewSection, etc.
│   ├── lib/
│   │   ├── api.ts                  # Fetch + WebSocket client
│   │   └── storage.ts              # localStorage dataset history
│   └── package.json
│
├── datasets/                       # Sample datasets for testing
├── pyproject.toml                  # emd package config
└── DOCUMENTATION.md
```

---

## 2. Running Locally

### Backend

```powershell
cd c:/Users/.../.../explain-my-data-CLI

# First time: install emd + backend deps
C:/.../.../anaconda3/python.exe -m pip install -e .
C:/.../.../anaconda3/python.exe -m pip install -r backend/requirements.txt

# Start (hot-reload)
C:/.../.../anaconda3/python.exe -m uvicorn backend.main:app --reload --port 8000
```

Swagger UI: `http://localhost:8000/docs`

### Frontend

```powershell
cd c:/.../.../.../explain-my-data-CLI/frontend
npm install
npm run dev         # http://localhost:3000
```

> Both must be running at the same time. Frontend expects backend at `http://localhost:8000` by default.

---

## 3. Backend

### 3.1 Architecture

The backend wraps the existing `emd` Python library in a FastAPI REST + WebSocket API. The computation layer (`src/emd/`) is completely unchanged — the backend simply calls the same analyzer classes that the CLI uses.

```
HTTP Request
    ↓
FastAPI Router (routers/jobs.py)
    ↓
Create Job (store.py) → return job_id immediately
    ↓
Background Task (Python thread)
    ↓
analysis_service.py → calls emd analyzers
    ↓
Update job.status / job.progress / job.result
    ↓
WebSocket /api/ws/{job_id} polls job every 400ms → streams to frontend
```

**Key design choices:**
- Analysis runs in a **background thread** (FastAPI `BackgroundTasks`). The HTTP endpoint returns instantly with a `job_id`.
- The **WebSocket** is a simple poller — every 400ms it reads the in-memory job object and pushes updates. No message queues needed.
- The **job store** is an in-memory Python dict. Data is lost on server restart. Suitable for MVP; upgrade to Redis for production.
- The `ChartRenderer` (matplotlib) is **not used** by the web API. Instead, raw chart-ready data (histogram bins, category counts, correlation matrices) is extracted from the analyzer result objects and sent as JSON. The frontend renders charts using **Recharts**.

---

### 3.2 Job Lifecycle

```
pending → running → done
                 → failed
```

| Status | Meaning |
|--------|---------|
| `pending` | Job created, background task not started yet |
| `running` | Background task active, `progress` 0–99, `step` shows current operation |
| `done` | `result` dict is populated, `progress` = 100 |
| `failed` | `error` string is set |

**Progress checkpoints (analyze):**

| Step | Progress |
|------|----------|
| Loading data | 5% |
| Quality check | 15% |
| Distribution analysis | 30% |
| Missing value analysis | 45% |
| Correlation analysis | 60% |
| Outlier detection | 75% |
| Target analysis (if set) | 85% |
| Building response | 95% |
| Done | 100% |

---

### 3.3 API Reference

#### `POST /api/jobs/analyze`

Upload a file and start a full EDA analysis job.

**Content-Type:** `multipart/form-data`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file` | File | required | CSV or Excel file |
| `skip_correlation` | bool | false | Skip correlation analysis |
| `skip_outlier` | bool | false | Skip outlier detection |
| `use_iforest` | bool | false | Add Isolation Forest method |
| `target` | string | "" | Target column for feature importance |
| `drop_cols` | string | "" | Comma-separated columns to drop |
| `parse_dates` | string | "" | Comma-separated date columns |
| `sample_size` | int | 0 | Row limit (0 = full dataset) |
| `sheet` | string | "" | Excel sheet name |

**Response:**
```json
{ "job_id": "uuid", "status": "pending" }
```

---

#### `POST /api/jobs/compare`

Start a drift detection job between two datasets.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reference` | File | required | Baseline dataset (training, historical) |
| `current` | File | required | New dataset (test, production) |
| `threshold` | float | 0.2 | PSI threshold for drift classification |

**Response:** `{ "job_id": "uuid", "status": "pending" }`

---

#### `POST /api/check`

Synchronous data quality check (no job, instant response).

| Field | Type | Description |
|-------|------|-------------|
| `file` | File | CSV or Excel file |

**Response:**
```json
{
  "filename": "data.csv",
  "shape": { "rows": 891, "cols": 12 },
  "quality": {
    "issues": [{ "check": "...", "severity": "WARNING", "result": "...", "recommendation": "..." }],
    "passed": true,
    "has_warnings": true
  }
}
```

---

#### `GET /api/jobs/{job_id}`

Poll job status.

**Response:**
```json
{
  "job_id": "uuid",
  "status": "done",
  "progress": 100,
  "step": "Done",
  "result": { ... },
  "error": null
}
```

Returns `404` if job not found.

---

#### `WebSocket /api/ws/{job_id}`

Real-time progress stream. Connect after getting `job_id`.

**Messages sent by server:**
```json
{ "status": "running", "progress": 45, "step": "Missing value analysis", "error": null }
```

Server closes the connection when `status` reaches `done` or `failed`.

---

### 3.4 Analysis Service

`backend/services/analysis_service.py`

Three public functions:

#### `run_analyze(job_id, file_bytes, filename, options, progress_cb) → dict`

Full EDA pipeline. Saves uploaded bytes to a temp file, runs all emd analyzers in sequence, calls `progress_cb(step_label, percent)` at each step, then assembles and returns the result dict.

**options keys:**
```python
{
  "skip_correlation": bool,
  "skip_outlier": bool,
  "use_iforest": bool,
  "target": str | None,
  "drop_cols": str,       # comma-separated
  "parse_dates": str,     # comma-separated
  "sample_size": int | None,
  "sheet": str | None,
}
```

#### `run_compare(job_id, ref_bytes, ref_name, cur_bytes, cur_name, options, progress_cb) → dict`

Drift analysis pipeline. Loads both files, runs `DriftAnalyzer`, builds overlay histograms for drifted numeric columns.

#### `run_check(file_bytes, filename) → dict`

Synchronous quality check. Returns filename, shape, and `QualityReport`.

---

### 3.5 Serializer & Chart Data

`backend/services/serializer.py`

#### `safe(obj) → Any`

Recursively makes any Python object JSON-serializable:
- `float` NaN/Inf → `None`
- `numpy.floating` / `numpy.integer` → Python float/int
- `pandas.DataFrame` → nested dict
- dataclasses → dict (via `dataclasses.asdict`)
- lists, tuples, dicts → recursed

#### Chart data builders (all return recharts-compatible lists):

| Function | Input | Output format |
|----------|-------|---------------|
| `numeric_histogram(series, bins=30)` | pd.Series | `[{bin, x, x1, count}]` |
| `categorical_bars(top_values)` | list of (value, count, pct) | `[{value, count, pct}]` |
| `corr_heatmap(df)` | pd.DataFrame | `[{row, col, value}]` |
| `missing_bars(missing_result)` | MissingResult | `[{column, missing_pct, missing_count}]` |
| `outlier_bars(outlier_result)` | OutlierResult | `[{column, IQR, IQR_extreme, Z_score, Modified_Z}]` |
| `drift_overlay(name, ref, cur, bins=25)` | two pd.Series | `[{bin, x, reference, current}]` |

---

### 3.6 JSON Response Schemas

#### Analyze result (`/api/jobs/{id}` → `result`)

```
result
├── overview
│   ├── filename, rows, cols, memory_kb
│   └── columns[]: { name, dtype, non_null, null_pct }
│
├── quality
│   ├── passed: bool
│   ├── has_warnings: bool
│   └── issues[]: { check, severity, result, recommendation }
│
├── distribution
│   ├── numeric[]:
│   │   ├── name, count, null_pct, mean, median, std
│   │   ├── skewness, excess_kurtosis, min, max, p25, p75
│   │   ├── normality_test, normality_pvalue, assumptions[]
│   │   ├── chart_data[]: { bin, x, x1, count }       ← histogram
│   │   └── box_data: { min, p25, p50, p75, max, mean }
│   └── categorical[]:
│       ├── name, count, null_pct, unique_count, entropy, assumptions[]
│       └── chart_data[]: { value, count, pct }        ← bar chart
│
├── missing
│   ├── global_missing_pct, total_missing, total_cells
│   ├── complete_rows, complete_rows_pct
│   ├── columns[]: { name, missing_count, missing_pct }
│   └── chart_data[]: { column, missing_pct, missing_count }
│
├── correlation (null if skipped)
│   ├── pearson[]: { row, col, value }                 ← heatmap flat list
│   ├── pearson_columns: string[]
│   ├── spearman[]: { row, col, value }
│   ├── spearman_columns: string[]
│   ├── cramers_v[]: { row, col, value }
│   ├── strong_pairs[]: { col_a, col_b, r, label }
│   ├── point_biserial[]: { num_col, bin_col, r, p }
│   ├── vif: { column: value } | null
│   └── warnings: string[]
│
├── outlier (null if skipped)
│   ├── methods_used: string[]
│   ├── columns[]: { name, iqr_count, iqr_pct, zscore_count, mzscore_count }
│   └── chart_data[]: { column, IQR, IQR_extreme, Z_score, Modified_Z }
│
└── target (null if not specified)
    ├── target_col, target_type
    ├── top_features[]: { feature, score, method, direction }
    └── warnings: string[]
```

#### Compare result (`/api/jobs/{id}` → `result`)

```
result
├── ref_name, cur_name
├── summary
│   ├── reference_shape, current_shape
│   ├── drifted_count, total_columns, drift_fraction
│   ├── overall_drift: bool
│   ├── missing_in_current: string[]
│   ├── new_in_current: string[]
│   └── psi_threshold
├── columns[]:
│   ├── name, col_type (numeric|categorical)
│   ├── psi, ks_pvalue, mean_shift_pct, chi2_pvalue
│   ├── drift_detected: bool
│   ├── drift_severity: none|moderate|high
│   └── mean_ref, mean_cur
├── drifted_columns: string[]
└── chart_data: { [column_name]: [{bin, x, reference, current}] }
```

---

## 4. Frontend

### 4.1 Architecture

**Stack:** Next.js 16 (App Router) · TypeScript · Tailwind CSS · Framer Motion · Recharts · React Dropzone · shadcn/ui

**Design philosophy:** Terminal-vibe dark theme. Smooth animations. Far from SPSS/EViews. Color palette:

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#06060d` | Page background |
| Surface | `#0d0d18` | Cards |
| Border | `#1c1c2e` | Dividers |
| Cyan | `#22d3ee` | Primary accent, analyze |
| Indigo | `#818cf8` | Compare / correlation |
| Emerald | `#34d399` | Success, batch, target |
| Amber | `#fbbf24` | Warnings, missing |
| Rose | `#f43f5e` | Errors, outliers |

---

### 4.2 Pages & Routes

| Route | File | Description |
|-------|------|-------------|
| `/` | `app/page.tsx` | Home dashboard — action cards + recent datasets |
| `/analyze` | `app/analyze/page.tsx` | Upload file → configure → analyze |
| `/report/[jobId]` | `app/report/[jobId]/page.tsx` | Full EDA results |
| `/compare` | `app/compare/page.tsx` | Upload two files → drift analysis |
| `/compare/result/[jobId]` | `app/compare/result/[jobId]/page.tsx` | Drift report |
| `/batch` | `app/batch/page.tsx` | Multi-file batch analysis |

---

### 4.3 Component Tree

```
layout.tsx (AppShell)
│
├── components/layout/AppShell.tsx
│   ├── Sidebar
│   │   ├── Logo / brand
│   │   ├── Nav buttons (New Analysis, Compare, Batch)
│   │   ├── Dataset history list (from localStorage)
│   │   └── Version footer
│   └── <children> (page content)
│
├── app/page.tsx                        Home
│
├── app/analyze/page.tsx                Upload flow
│   ├── components/upload/UploadZone.tsx
│   ├── components/upload/AnalysisOptions.tsx
│   └── components/upload/JobProgress.tsx
│
├── app/report/[jobId]/page.tsx         EDA results
│   └── components/report/ReportLayout.tsx
│       ├── QualitySection.tsx          (always visible)
│       ├── OverviewSection.tsx         (always visible)
│       └── [toggle buttons]
│           ├── DistributionSection.tsx
│           ├── CorrelationSection.tsx
│           ├── MissingSection.tsx
│           ├── OutlierSection.tsx
│           └── Target (inline)
│
├── app/compare/page.tsx                Drift upload
│   └── components/compare/CompareUpload.tsx
│
├── app/compare/result/[jobId]/page.tsx Drift results
│   └── components/compare/DriftReport.tsx
│
└── app/batch/page.tsx                  Batch queue
    └── components/batch/BatchQueue.tsx
```

---

### 4.4 Upload Flow

The analyze flow (`/analyze`) is a client-side state machine:

```
idle
 └─ (file dropped) ──→ options
                          └─ (Analyze clicked) ──→ progress
                                                      ├─ (done) ──→ /report/[jobId]
                                                      └─ (error) ──→ error (retry)
```

**`UploadZone`** — accepts CSV/XLSX via drag-and-drop or browse. Max 100 MB. Shows file name + size after selection.

**`AnalysisOptions`** — collapsible panel with:
- Target column (for feature importance)
- Sample size (for large files)
- Skip correlation / skip outlier toggles
- Gradient "Analyze" button

**`JobProgress`** — WebSocket client. Uses `intentionallyClosed` flag to avoid spurious errors when React StrictMode double-fires effects. Callback refs (`onDoneRef`, `onErrorRef`) prevent reconnects when parent re-renders.

On completion, calls `saveDataset(...)` (localStorage) then routes to `/report/{jobId}`.

---

### 4.5 Report Layout

`components/report/ReportLayout.tsx`

**Quality + Overview** are always rendered on page load — they are fast to display and immediately useful.

**Deep dive sections** (Distribution, Correlation, Missing, Outliers, Target) are behind toggle buttons. Each button:
- Shows only if the data exists (e.g. no Correlation button if correlation was skipped)
- Toggles open/closed with Framer Motion height animation
- Multiple sections can be open simultaneously
- Opening adds a colored accent line above the section

```
┌──────────────────────────────────────────────┐
│  Data Quality        ← always visible         │
│  Dataset Overview    ← always visible         │
│                                              │
│  Deep dive:                                  │
│  [Distribution] [Correlation] [Outliers]     │
│                                              │
│  ──────── cyan accent line ────────          │
│  Distribution Section (expanded)             │
│                                              │
│  ──────── rose accent line ────────          │
│  Outlier Section (expanded)                  │
└──────────────────────────────────────────────┘
```

---

### 4.6 Dataset History

`frontend/lib/storage.ts`

Datasets are saved to `localStorage` under the key `emd_datasets`. Each entry:

```typescript
{
  id: string;          // random ID
  type: "analyze" | "compare" | "batch";
  label: string;       // "iris.csv", "train.csv vs test.csv", etc.
  jobId: string;       // backend job ID
  href: string;        // "/report/{jobId}" or "/compare/result/{jobId}"
  createdAt: number;   // timestamp
}
```

**When datasets are saved:**
- `/analyze` → on `handleDone` (before redirect)
- `/compare` → on `handleDone` (before redirect)
- `/batch` → per-file, inside `useBatchItem` hook when WebSocket reports `done`

**Reactivity:** Any write dispatches a custom `emd_storage` window event. `AppShell` and `HomePage` both listen to this event and re-read localStorage immediately.

**Limits:** Max 50 entries (oldest trimmed). Duplicates by `jobId` are replaced, not appended.

---

### 4.7 API Client

`frontend/lib/api.ts`

Base URL: `NEXT_PUBLIC_API_URL` env var, defaults to `http://localhost:8000`.

```typescript
// Upload file and start analysis job
uploadAndAnalyze(file: File, options: AnalyzeOptions): Promise<JobCreated>

// Upload two files and start drift comparison
uploadAndCompare(reference: File, current: File, threshold?: number): Promise<JobCreated>

// Poll job status + result
getJobStatus(jobId: string): Promise<JobStatus>

// Open WebSocket for real-time progress
createJobSocket(jobId: string): WebSocket
// → connects to ws://localhost:8000/api/ws/{jobId}
// → server sends: { status, progress, step, error }
// → server closes connection when done or failed
```

All types are exported from `api.ts` and used throughout the codebase for consistency.

---

## 5. Deployment

### Frontend → Vercel

1. Connect repo to Vercel
2. Set **Root Directory** to `frontend`
3. Set env var: `NEXT_PUBLIC_API_URL=https://your-backend.railway.app`
4. Deploy

### Backend → Railway

1. Connect repo to Railway
2. Set **Root Directory** to project root (Dockerfile handles the rest)
3. Set env var: `ALLOWED_ORIGINS=https://your-app.vercel.app`
4. Railway auto-detects Dockerfile and builds

**Dockerfile flow:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
# Copy emd source + install
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install -e .
# Install backend deps
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt
# Copy backend code + start
COPY backend/ ./backend/
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Cost estimate:** Frontend free on Vercel · Backend ~$5–10/month on Railway starter.

---

## 6. Environment Variables

| Variable | Where | Default | Description |
|----------|-------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | Frontend `.env.local` | `http://localhost:8000` | Backend base URL |
| `ALLOWED_ORIGINS` | Backend (Railway env) | _(empty)_ | Extra CORS origins, comma-separated |

---

## Notes & Known Limitations

- **Job store is in-memory.** Server restart clears all jobs. The frontend saves job IDs in localStorage, so old links will 404 after a restart.
- **No authentication.** All jobs and data are anonymous. Do not deploy publicly with sensitive data.
- **File size.** Max 100 MB enforced on the frontend; the backend has no explicit limit but large files will strain memory on small Railway instances. Use `sample_size` for datasets > 200k rows.
- **Matplotlib not used by the API.** Charts are rendered in the browser via Recharts from structured JSON. The `ChartRenderer` class is still used by the CLI but not by the web backend.
- **WebSocket reconnection.** Not implemented. If the connection drops mid-analysis, the user sees "Connection lost" and can retry by navigating back.
