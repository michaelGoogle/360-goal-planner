# 360-Goal Planner (GP)

Direct-to-customer Goal Planner. React UI + FastAPI BFF. **People Like You /
Need Profiler / Need Calculator** run in-process. **HU** (HappiU) and **SV**
(Scenario Visualizer) stay upstream. GP does not run Monte Carlo itself.

This repo is GP only. Point `HU_UPSTREAM` and `SV_UPSTREAM` at the engines you
have been given. See [docs/Standalone-third-party.md](docs/Standalone-third-party.md).

**Full documentation:** [`docs/README.md`](docs/README.md)

## Quick start

```powershell
copy .env.example .env   # then edit upstream URLs / keys
pip install -e ".[dev]"
python run_server.py          # http://127.0.0.1:8009

cd frontend
npm install
npm run dev                   # http://127.0.0.1:5179  (proxies /v1 → :8009)
```

Or: `docker compose up -d --build` → http://127.0.0.1:8069

OpenAPI: `/docs`.

## API

See [docs/API.md](docs/API.md). How People Like You / Need Profiler / Need Calculator work: [docs/People-like-you-and-needs.md](docs/People-like-you-and-needs.md). Other formulas: [docs/Calculations.md](docs/Calculations.md). Short form:

| Method | Path | Role |
|--------|------|------|
| `POST` | `/v1/parse-sentence` | About You extract (OpenAI) |
| `POST` | `/v1/predict` | In-process PLU → profiler → calculator (503 if PLU cannot run) |
| `POST` | `/v1/score` | HU HappiU |
| `POST` | `/v1/project` | SV wealth path |
| `POST` | `/v1/explain` | Spoken Mira / page explainers |
| `GET` | `/health` `/healthz` | Liveness |

## Env

| Variable | Default | Meaning |
|----------|---------|---------|
| `FM_UPSTREAM` | `http://127.0.0.1:8062` | Optional FM (HeyGen plan-report snapshot; not Estimate) |
| `HU_UPSTREAM` | `http://127.0.0.1:8002` | HappiU |
| `SV_UPSTREAM` | `http://127.0.0.1:8001` | Scenario Visualizer |
| `APP_PORT` | `8009` | Listen port |
| `OPENAI_API_KEY` | — | Sentence extract + explainers |
| `OPENAI_API_MODEL` | `gpt-4o-mini` | Chat model |

Audio prompts: [`src/prompts/`](src/prompts/). Never commit a real key.

## Tests

```powershell
python -m pytest tests/ -q
python -m ruff check src tests
```
