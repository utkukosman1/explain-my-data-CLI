# Web UI (optional)

`emd` is a CLI tool — this is an optional companion for people who'd rather use a browser. It's not required to use `emd`.

- `backend/` — a FastAPI service that wraps the same `src/emd/` analyzer classes the CLI uses, exposed as a JSON/WebSocket API.
- `frontend/` — a Next.js app that uploads files to the backend and renders the results with Recharts.

## Running it locally

Both must run at the same time; the frontend expects the backend at `http://localhost:8000` by default.

```bash
# from repo root
pip install -e .
pip install -r web/backend/requirements.txt
uvicorn web.backend.main:app --reload --port 8000   # http://localhost:8000/docs
```

```bash
cd web/frontend
npm install
npm run dev                                          # http://localhost:3000
```

## Environment variables

| Variable | Where | Default | Description |
|----------|-------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | Frontend `.env.local` | `http://localhost:8000` | Backend base URL |
| `ALLOWED_ORIGINS` | Backend environment | _(empty)_ | Extra CORS origins, comma-separated |

## Known limitations

- The job store is in-memory — a backend restart clears all jobs, and old frontend links (saved in `localStorage`) will 404 afterward.
- No authentication. Don't deploy this publicly with sensitive data.
- Max upload size is enforced client-side (100 MB); for larger datasets, use `sample_size`.
