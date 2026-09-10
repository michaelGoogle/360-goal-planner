# Getting started — run and access 360-Goal Planner

This guide covers how to start the **GP BFF** and the **React UI**, and which
URLs to open.

For HTTP contracts see [API.md](API.md). For internals see
[Architecture.md](Architecture.md).

---

## What you run

| Component | Role | Default URL |
|-----------|------|-------------|
| **GP BFF** (bare metal) | FastAPI: predict / score / project / explain | http://127.0.0.1:8009 |
| **GP UI** (Vite) | Customer journey; proxies `/v1` → `:8009` | http://127.0.0.1:5179 |
| **GP** (Docker Compose) | BFF + baked `frontend/dist` at `/` | http://127.0.0.1:8069 |
| **GP** (WAN / Synology) | Same as compose, reverse-proxied | https://mgzh11.synology.me:8469 |

OpenAPI: http://127.0.0.1:8009/docs (bare) · http://127.0.0.1:8069/docs (Docker)

GP needs **FM**, **HU**, and **SV** for a full journey. Without FM, About You
still works but Estimate returns **503**. Your score / Your plan fail until
HappiU and Scenario Visualizer are up.

---

## Prerequisites

- Python **3.13** (`requires-python = ">=3.13,<3.14"` in `pyproject.toml`).
- **Node.js 20+** / **npm** for the Vite UI.
- Optional: **Docker Desktop** with Compose v2.
- Optional: `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) for People Like You, sentence extract, and spoken explainers.

---

## Bare-metal BFF + Vite UI (typical local)

From two terminals:

```powershell
# from this repo root
pip install -e ".[dev]"
python run_server.py          # uvicorn @ 127.0.0.1:8009
```

```powershell
cd frontend
npm install
npm run dev                   # http://127.0.0.1:5179
```

Open **http://127.0.0.1:5179**. Vite proxies `/v1` and `/health` to `:8009`, and
`/fm` to FM on `:8062` (auth handoff).

Health: http://127.0.0.1:8009/health · OpenAPI: http://127.0.0.1:8009/docs

Point the BFF at local engines if they are not on the defaults:

```powershell
$env:FM_UPSTREAM = "http://127.0.0.1:8003"   # FM run_server.py default
$env:HU_UPSTREAM = "http://127.0.0.1:8002"
$env:SV_UPSTREAM = "http://127.0.0.1:8001"
python run_server.py
```

`src/upstream.py` defaults: FM **8062** (compose), HU **8002**, SV **8001**.

---

## Docker stack

From this repo root:

```powershell
docker compose up -d --build
```

Compose starts `fm`, `hu`, and `sv` as dependencies. UI + API:
http://127.0.0.1:8069 · OpenAPI: http://127.0.0.1:8069/docs

Image: `deployment/docker/GP.Dockerfile` (Node build of `frontend/dist`, then
Python runtime). Env inside the container: `FM_UPSTREAM=http://fm:8062`,
`HU_UPSTREAM=http://hu:8063`, `SV_UPSTREAM=http://sv:8064`.

---

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `APP_PORT` / `GP_PORT` | `8009` (bare) / `8069` (compose) | Listen port |
| `GP_HOST` | `127.0.0.1` | Bind host (`run_server.py`) |
| `FM_UPSTREAM` | `http://127.0.0.1:8062` | Optional FM (HeyGen plan-report; not Estimate) |
| `HU_UPSTREAM` | `http://127.0.0.1:8002` | `POST /v1/happi-u` |
| `SV_UPSTREAM` | `http://127.0.0.1:8001` | `POST /api/v2/scenario-visualizer` |
| `GP_UPSTREAM_TIMEOUT_S` | `90` | Upstream HTTP timeout |
| `ANTHROPIC_API_KEY` | — | People Like You (preferred) and parse-sentence |
| `OPENAI_API_KEY` | — | Fallback LLM; spoken explainers |
| `OPENAI_API_MODEL` | `gpt-4o-mini` | Chat model id |
| `GP_FRONTEND_DIST` | `frontend/dist` | Directory mounted at `/` when present |
| `GP_RELOAD` | — | `1` / `true` enables uvicorn `--reload` |

Never commit a real API key. Workspace `.env` / compose pass `OPENAI_API_KEY`
through to `gp`.

---

## Tests (smoke)

```powershell
# from this repo root
python -m pytest tests/ -q
python -m ruff check src tests
```

Frontend: `cd frontend && npx tsc -b`. Full procedure: [Testing.md](Testing.md).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Vite `/v1/...` proxy error `ECONNREFUSED :8009` | BFF not running | `python run_server.py` in the repo root |
| Your money / Estimate 503 | People Like You cannot run (no LLM key, or model error) | Set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) in workspace `.env` |
| Your score / plan 503 | HU or SV down | Start those services; check `HU_UPSTREAM` / `SV_UPSTREAM` |
| Explainers sound canned | No `OPENAI_API_KEY` on GP | Set the key; `source` on `/v1/explain` will be `llm` |
| Empty UI on `:8069` | Image built without `frontend/dist` | Rebuild `gp` (Dockerfile always builds the UI) |

---

## Next

- HTTP details: [API.md](API.md)
- Internals: [Architecture.md](Architecture.md)
- Product intent: [Business-overview.md](Business-overview.md)
