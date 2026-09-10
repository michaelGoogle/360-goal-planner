# 360-Goal Planner — architecture

## Role in the suite

```text
Customer (React UI)
        │
        ▼
GP BFF  (FastAPI)
        ├── POST /v1/parse-sentence  → OpenAI (About You fields)
        ├── POST /v1/explain         → OpenAI + src/prompts/*.md
        ├── POST /v1/predict         → People Like You / Need Profiler / Need Calculator
        │                            (in-process; 503 if People Like You cannot run)
        ├── POST /v1/score           → HU POST /v1/happi-u
        └── POST /v1/project         → SV POST /api/v2/scenario-visualizer
```

GP is a **customer UI + BFF**. People Like You / Need Profiler / Need Calculator
run in-process. HappiU and the chart stay in HU / SV. Mapping to those engines
lives in `hu_payload.py` / `sv_payload.py`. Prompts instruct the model to use
only the JSON context the UI already displayed.

## Stack

- **Backend:** FastAPI + uvicorn, Python 3.13, `openai`, `requests` / `httpx`.
- **Frontend:** React 19, Vite 8 (`:5179`), Tailwind 4. Plotly for the plan chart.
- **Compose:** `deployment/docker/GP.Dockerfile` bakes `frontend/dist` and
  serves it from the API process when that folder exists.

## Modules

| Path | Role |
|------|------|
| [`src/app.py`](../src/app.py) | FastAPI factory, CORS, routes, static UI mount |
| [`src/predict.py`](../src/predict.py) | People Like You / profiler / calculator session mapping |
| [`src/upstream.py`](../src/upstream.py) | FM / HU / SV HTTP helpers and timeouts |
| [`src/openai_client.py`](../src/openai_client.py) | Shared OpenAI chat helper |
| [`src/hu_payload.py`](../src/hu_payload.py) | Session → HappiU `POST /v1/happi-u` body |
| [`src/sv_payload.py`](../src/sv_payload.py) | Session → SV scenario-visualizer body |
| [`src/parse_sentence.py`](../src/parse_sentence.py) | OpenAI extract of About You fields |
| [`src/explain.py`](../src/explain.py) | Load prompts, call OpenAI, deterministic fallback |
| [`src/prompts/*.md`](../src/prompts/) | Mira / page explainer prompts |
| [`frontend/src/`](../frontend/src/) | Shell, five pages, session state, speech |
| [`run_server.py`](../run_server.py) | uvicorn entry (`src.app:api`) |

## Request lifecycle

### Predict (`POST /v1/predict`)

1. Normalize session (synthesize `dateOfBirth` from age if missing).
2. Run **People Like You** in-process (`src/pipeline/run.py`).
3. On success, map finance + optional assumed life cover (mortgage rounded to
   S$100k, or 5× annual income when there is at least one dependant).
4. On People Like You failure, return **503** (no occupation-band fallback).
5. Need Profiler (`topN=5`, including the PLU lifestyle blob) then Need
   Calculator (`onlyEmpty=true`), also in-process.
6. Return `{ success, session, notes }`. Notes list which steps were skipped.

How People Like You, Need Profiler, and Need Calculator work is in
[People-like-you-and-needs.md](People-like-you-and-needs.md). Goal-card
recalc, suggested plan, and budget are in [Calculations.md](Calculations.md).

### Score / project

`build_happiu_payload` / `build_sv_payload` turn the same session into engine
JSON. HU/SV errors surface as **503** (unreachable) or the upstream status.
SV is called with `tenant_id=helium`.

### Explain (`POST /v1/explain`)

1. Validate `kind` ∈ `{mira, intro, money, score, chart, prod}`.
2. Mira also needs `route` ∈ `{d2cIntro, d2cAbout, d2cMoney, d2cScore, d2cPlan}`.
3. Load `voice.md` + the kind/route task file (Mira on money/score also
   concatenates `money.md` / `score.md`).
4. If `OPENAI_API_KEY` is set, chat completion (`temperature=0.4`); on failure
   or short output, use `fallback_script`.
5. Return `{ text, source: "llm" | "fallback" }`.

The UI builds a compact **context** object (figures, gaps, chart endpoints) in
[`frontend/src/lib/explain.ts`](../frontend/src/lib/explain.ts) so the model
never sees full SV year arrays.

## Prompts

Plain Markdown under `src/prompts/`. Edit them to change spoken tone without
changing Python.

| File | Trigger |
|------|---------|
| `voice.md` | Prepended to every explainer |
| `mira_intro.md` … `mira_plan.md` | Mira FAB on that screen |
| `intro.md` | Start — “Hear what you get” |
| `money.md` | “Explain these figures” |
| `score.md` | “Explain this page” |
| `chart.md` | “Explain this chart” |
| `products.md` | “Why these products” |

## Frontend

Single-page app (`App.tsx`) holds the session and route. `Shell` is the chrome
(progress nav, Mira + human-adviser FABs). Pages: `Intro`, `AboutYou`, `Money`,
`Score`, `Plan`. Speech: Web Speech API (`lib/speech.ts`). Optional portal JWT
hash (`#siriheritage_auth=`) via `lib/auth.ts`.

When `frontend/dist` exists, FastAPI mounts it at `/` **after** the API routes,
so `/v1/*` still hits the BFF.

## Auth

No login required. If the portal hands off a JWT, `predict` can persist
onboarding to FM (`/v1/me/onboarding/...`). Public FM paths are used otherwise.
