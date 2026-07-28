# AGENTS.md

Guidance for Codex when working in this repo. **This file is gitignored — never commit or push it.**

## Project

`emd` — automated EDA CLI. Three layers, shared computation:

1. **`src/emd/`** — core library + Typer CLI. Loads CSV/XLSX, runs analyzers, renders matplotlib/seaborn charts, writes Markdown (+ optional JSON) report.
2. **`web/backend/`** — FastAPI wrapper around `src/emd/`. Does **not** use `ChartRenderer`; extracts chart-ready JSON (bins/counts/matrices) for Recharts instead.
3. **`web/frontend/`** — Next.js 16 (TS/Tailwind/Recharts) over REST + WebSocket. Has its own [web/frontend/AGENTS.md](web/frontend/AGENTS.md) → read `web/frontend/AGENTS.md` before writing Next.js code (this version has breaking API changes vs. training data; check `node_modules/next/dist/docs/`).

`src/emd/analysis/` analyzer classes are shared by CLI and backend — keep that layer UI-agnostic.

Docs: [web/README.md](web/README.md) (web setup) · [docs/cli-reference.md](docs/cli-reference.md) (flags) · [docs/statistical-methods.md](docs/statistical-methods.md) (stats methods).

## Product principles

The CLI is the product; the web UI is a secondary companion. Goal: help users understand a new dataset as fast as possible. Prioritize simplicity, terminal-first UX, and improving existing workflows over adding new commands. Before adding a feature, check it actually speeds up a user's first 15 minutes with a new dataset.

## Working rules

- No assumptions on ambiguous requirements — ask.
- Focused changes only; don't refactor unrelated code.
- Explain non-obvious architectural trade-offs before implementing.
- Never add a `Co-Authored-By: Codex` (or similar AI attribution) trailer to commits.

## Commands

```bash
pip install -e ".[dev]"                          # emd + pytest/ruff/mypy
pip install -e ".[ml]"                            # optional: scikit-learn for Isolation Forest

pytest tests/                                     # coverage on src/emd enabled via pyproject addopts
pytest tests/test_correlation.py::test_name -v    # single test

ruff check src/ tests/
mypy src/emd

emd analyze data.csv                              # full report (report.md + charts)
emd summary data.csv                              # terminal-only recap, nothing written to disk
emd doctor data.csv                               # health score + pre-modeling risk audit
emd compare train.csv test.csv                    # drift between two datasets
emd check data.csv
emd schema init data.csv
emd schema validate data.csv --schema schema.yaml
```

Web (optional, both must run together): `uvicorn web.backend.main:app --reload --port 8000` (from repo root) and `cd web/frontend && npm run dev` (http://localhost:3000, backend URL via `NEXT_PUBLIC_API_URL`).

## Architecture

### `src/emd/`

- `cli/` — Typer app split per command: `_app.py` (app + version callback), `_ui.py` (consoles, colors, `Steps` checklist, `header`/`output_panel`/`make_table`), `_pipeline.py` (shared load → prepare → quality gate → `run_analyzers` sequence used by analyze/summary/doctor), and one module per command (`analyze.py`, `summary.py`, `doctor.py`, `compare.py`, `check.py`, `batch.py`, `sheets.py`, `info.py`, `schema.py`). `__init__.py` imports the command modules to register them, keeping the `emd.cli:app` entry point. Heavy imports live inside command functions to keep startup fast. `analyze` runs analyzers concurrently (`ThreadPoolExecutor` in `_pipeline.run_analyzers`), then charts + report sequentially; `summary` and `doctor` reuse the same pipeline without charts.
- `loader/` — `CSVLoader` (chardet + delimiter detection), `XLSXLoader` (sheet selection).
- `quality/checker.py` — `QualityChecker`: FATAL/WARNING/INFO gate before analysis (empty data, high-missing cols, dupes, mixed types).
- `analysis/` — one analyzer per concern, each `.analyze(df)` → typed dataclass: `distribution.py`, `correlation.py` (Pearson/Spearman/Cramér's V/VIF), `missing.py`, `outlier.py` (IQR/Z/Modified-Z/optional Isolation Forest), `target.py`, `drift.py` (PSI/KS/Chi-squared).
- `charts/renderer.py` — matplotlib/seaborn PNG/SVG. **CLI-only**, backend never imports it.
- `report/generator.py` — `MarkdownReportGenerator`: analyzer results + chart paths → `report.md`, optionally `analysis_results.json` (stable contract, also used by backend).
- `schema/` — `ContractGenerator`/`SchemaValidator`/`contract.py` (YAML schema contracts, `SchemaContract`/`ColumnRule`/`GlobalRule`). Contracts live under `datasets/schemas/`.
- `config.py` — `ReportConfig`: dataclass threading options through the `analyze` CLI pipeline (`cli/analyze.py`). **CLI-only** — the web backend builds its own options dict in `web/backend/services/analysis_service.py`. Every field must have a downstream consumer; don't add speculative knobs.

### `web/backend/` (optional)

- `store.py` — in-memory job dict (`pending → running → done|failed`). **Lost on restart — intentional for the MVP**, not a bug.
- `routers/jobs.py` — HTTP endpoints + `WebSocket /api/ws/{job_id}` (polls job every 400ms, streams `{status, progress, step, error}`).
- `services/analysis_service.py` — `run_analyze`/`run_compare`/`run_check`, orchestrating the same analyzer classes as the CLI via a `progress_cb` callback; runs in a background thread, returns `job_id` immediately.
- `services/serializer.py` — `safe(obj)` makes analyzer results JSON-safe (NaN/Inf→`None`, numpy→scalars, dataclass→dict) + chart-data builders for Recharts. New analyzer fields the frontend needs go through here. This file defines the response shape the frontend depends on — check it before changing result shapes.

### `web/frontend/` (optional)

Next.js 16 App Router, TS, Tailwind, Recharts, shadcn/ui.

- `lib/api.ts` — typed fetch/WebSocket client.
- `lib/storage.ts` — dataset history in `localStorage` (key `emd_datasets`, max 50, dedup by `jobId`), dispatches `emd_storage` event on write.
- `app/analyze|compare|batch` — upload/configure/progress state machines (`idle → options → progress → done|error`).
- `app/report/[jobId]`, `app/compare/result/[jobId]` — result pages; `ReportLayout.tsx` always shows Quality + Overview, other sections toggle on if present in the job result.

## Key conventions

- Analyzer output is dataclasses (`*Result`/`*Stats`), not dicts — both the report generator and backend serializer expect structured objects.
- Extend `ReportConfig` rather than threading new ad-hoc params through the call chain.
- `analysis_results.json` (from `--output-json`) is a stable external contract — changing its shape is breaking.
- ruff: line length 100, py311 target, rules `E, F, I, N, UP, B, SIM` (`pyproject.toml`). Python ≥3.11 required.
