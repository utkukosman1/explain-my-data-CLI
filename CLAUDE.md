# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Explain My Data (`emd`) is an automated EDA (exploratory data analysis) tool with three layers:

1. **`src/emd/`** — the core Python library and CLI (Typer). Loads a CSV/XLSX, runs statistical analyzers, renders matplotlib/seaborn charts, and writes a Markdown (+ optional JSON) report.
2. **`web/backend/`** — a FastAPI web API that wraps `src/emd/` for the web frontend. It does **not** use `ChartRenderer`; instead it extracts chart-ready data (bins, counts, matrices) as JSON for the frontend to render with Recharts.
3. **`web/frontend/`** — a Next.js 16 app (TypeScript, Tailwind, Recharts) that talks to the backend over REST + WebSocket. It has its own [web/frontend/CLAUDE.md](web/frontend/CLAUDE.md) (currently just points to `web/frontend/AGENTS.md`, which warns that this Next.js version has breaking API changes from training data — check `node_modules/next/dist/docs/` before writing Next.js code).

The CLI and backend both call the same analyzer classes in `src/emd/analysis/` — that computation layer is shared and must stay UI-agnostic.

Optional web UI setup and notes: [web/README.md](web/README.md). CLI flag reference: [docs/cli-reference.md](docs/cli-reference.md). Stats method explanations: [docs/statistical-methods.md](docs/statistical-methods.md).


## Product Principles

`emd` is a developer-first CLI tool.

The CLI is the product.

The web interface is an optional companion and must never become the primary focus.

The goal of `emd` is simple:

> Help users understand a new dataset as quickly as possible.

When making decisions, prioritize:

- Simplicity over complexity.
- Developer experience over feature count.
- Improving existing workflows over adding new commands.
- Clear, actionable reports over raw statistics.
- Terminal-first workflows over web-first workflows.

Before implementing a feature, ask:

1. Does this improve the first exploratory analysis of a dataset?
2. Does this make `emd` more useful from the terminal?
3. Would a real user benefit from this within the first 15 minutes?

If the answer is "no", reconsider the implementation.

When working on this repository:

- Do not make assumptions.
- Ask for clarification when requirements are ambiguous.
- Make focused, incremental changes.
- Do not refactor unrelated code.
- Explain important architectural trade-offs before implementing them.
- When pushing a commit, never add a `Co-Authored-By: Claude` (or similar AI attribution) trailer.

## Commands

### Python (CLI + web/backend) — run from repo root

```bash
pip install -e ".[dev]"          # install emd + dev deps (pytest, ruff, mypy)
pip install -e ".[ml]"           # optional: adds scikit-learn for Isolation Forest outlier detection

pytest tests/                    # run all tests (coverage on src/emd is enabled via pyproject addopts)
pytest tests/test_correlation.py -v      # single test file
pytest tests/test_correlation.py::test_name -v   # single test

ruff check src/ tests/           # lint
mypy src/emd                     # type check

emd analyze data.csv             # run the CLI directly (entry point defined in pyproject.toml)
emd summary data.csv             # fast terminal recap only — no charts/report/JSON written
emd compare train.csv test.csv
emd check data.csv
emd schema init data.csv
emd schema validate data.csv --schema schema.yaml
```

### Backend (FastAPI) — optional, lives under web/

```bash
pip install -r web/backend/requirements.txt
uvicorn web.backend.main:app --reload --port 8000    # run from repo root; http://localhost:8000/docs for Swagger UI
```

The frontend expects the backend at `http://localhost:8000` by default (override with `NEXT_PUBLIC_API_URL`).

### Frontend (Next.js) — optional, lives under web/

```bash
cd web/frontend
npm install
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

Both backend and frontend must run simultaneously for the web app to work end-to-end.

## Architecture

### `src/emd/` — computation library

- `cli.py` — single Typer app with all commands (`analyze`, `summary`, `compare`, `check`, `batch`, `sheets`, `info`, `schema init`, `schema validate`). Imports inside command functions (not top-level) to keep CLI startup fast. `summary` prints a terminal-only Key Issues + At a Glance recap built from the same analyzers as `analyze`, but writes nothing to disk (no charts, no report, no JSON) — see `_render_summary`/`_summary_key_issues`/`_summary_at_a_glance`.
- `loader/` — `CSVLoader` (auto-detects encoding via chardet and delimiter) and `XLSXLoader` (sheet selection).
- `quality/checker.py` — `QualityChecker` runs FATAL/WARNING/INFO gate checks (empty data, high-missing columns, duplicate rows, mixed types) before analysis proceeds.
- `analysis/` — one analyzer class per concern, each with an `.analyze(df)` method returning a typed result dataclass: `distribution.py` (numeric + categorical stats, normality tests), `correlation.py` (Pearson/Spearman/Cramér's V/VIF), `missing.py` (missingness patterns + correlated missingness), `outlier.py` (IQR/Z-score/Modified-Z/optional Isolation Forest), `target.py` (feature importance vs. a target column), `drift.py` (PSI/KS-test/Chi-squared between two datasets).
- `charts/renderer.py` — `ChartRenderer` produces matplotlib/seaborn PNG/SVG files. **CLI-only** — the backend never imports this.
- `report/generator.py` — `MarkdownReportGenerator` assembles analyzer results + chart paths into `report.md`, and can also emit `analysis_results.json` (the stable JSON contract used by downstream consumers, including the backend).
- `schema/` — `ContractGenerator` infers a YAML schema contract from a dataframe (`schema/generator.py`), `SchemaValidator` checks a dataframe against a saved contract (`schema/validator.py`), and `contract.py` defines the `SchemaContract`/`ColumnRule`/`GlobalRule` dataclasses plus YAML load/save. Contracts live under `datasets/schemas/`.
- `config.py` — `ReportConfig` is the single dataclass threading options (thresholds, output dir, flags) through the whole pipeline; both `cli.py` and `web/backend/services/analysis_service.py` construct it from user input.

`analyze` in `cli.py` runs distribution/missing/correlation/outlier/target analyzers concurrently via `ThreadPoolExecutor`, then renders charts and the report sequentially.

### `web/backend/` — FastAPI wrapper (optional)

- `main.py` — app instance + CORS (reads `ALLOWED_ORIGINS` env var).
- `store.py` — in-memory job dict (`pending → running → done|failed`). **Lost on restart** — this is intentional for the MVP, not a bug to fix reflexively.
- `routers/jobs.py` — all HTTP endpoints plus `WebSocket /api/ws/{job_id}`, which polls the in-memory job every 400ms and streams `{status, progress, step, error}` until done/failed.
- `services/analysis_service.py` — `run_analyze`, `run_compare`, `run_check`. Orchestrates the same `emd` analyzer classes the CLI uses, via a `progress_cb(step_label, percent)` callback for the WebSocket updates. Analysis runs in a background thread (FastAPI `BackgroundTasks`); the HTTP endpoint returns a `job_id` immediately.
- `services/serializer.py` — `safe(obj)` recursively makes analyzer result objects JSON-safe (NaN/Inf → `None`, numpy → Python scalars, dataclasses → dict), plus chart-data builders (`numeric_histogram`, `categorical_bars`, `corr_heatmap`, `missing_bars`, `outlier_bars`, `drift_overlay`) that produce Recharts-compatible arrays. This is where "analyzer result → frontend chart JSON" translation happens — if you add a new analyzer field the frontend needs, it goes through here.

The exact JSON response shape for `analyze`/`compare` jobs lives in `web/backend/services/serializer.py` — consult it before changing result shapes, since the frontend depends on the exact keys.

### `web/frontend/` — Next.js app (optional)

Stack: Next.js 16 (App Router), TypeScript, Tailwind, Framer Motion, Recharts, react-dropzone, shadcn/ui.

- `lib/api.ts` — typed fetch/WebSocket client (`uploadAndAnalyze`, `uploadAndCompare`, `getJobStatus`, `createJobSocket`); base URL from `NEXT_PUBLIC_API_URL`.
- `lib/storage.ts` — dataset history persisted to `localStorage` (key `emd_datasets`, max 50 entries, dedup by `jobId`); writes dispatch a custom `emd_storage` event that `AppShell`/`HomePage` listen for.
- `app/analyze`, `app/compare`, `app/batch` — upload/configure/progress flows, each a client-side state machine (`idle → options → progress → done|error`).
- `app/report/[jobId]`, `app/compare/result/[jobId]` — result pages. `components/report/ReportLayout.tsx` always shows Quality + Overview; Distribution/Correlation/Missing/Outlier/Target sections are behind toggle buttons that only appear if that data exists in the job result.

Before writing Next.js code, read `web/frontend/AGENTS.md` — it warns this Next.js version differs from training-data conventions and to check `node_modules/next/dist/docs/` first.

## Key conventions

- Analyzer results are dataclasses, not dicts — new analysis output should follow the same pattern (a `*Result`/`*Stats` dataclass returned from `.analyze()`), since both the Markdown generator and the backend serializer expect structured objects.
- `ReportConfig` (`src/emd/config.py`) is the single source of truth for pipeline options — extend it rather than passing new ad-hoc parameters through the call chain.
- The JSON emitted by `--output-json` (`analysis_results.json`) is a stable contract for external consumers; changing its shape is a breaking change.
- `ruff` config: line length 100, target py311, rule sets `E, F, I, N, UP, B, SIM` (see `pyproject.toml`).
- Requires Python ≥3.11 (`.python-version` pins 3.11).
