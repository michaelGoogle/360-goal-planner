# 360-Goal Planner (GP) — documentation

Direct-to-customer **Goal Planner**: a React UI plus a FastAPI BFF. **People
Like You / Need Profiler / Need Calculator** run in-process. The BFF maps the
session into **HU** (HappiU score) and **SV** (wealth projection). GP does
**not** run Monte Carlo itself.

Branded in the UI as **FinPlan360 · Powered by 360F**.

## Doc map

| Doc | Audience | Covers |
|-----|----------|--------|
| [Getting-started.md](Getting-started.md) | Developers | Install, env, local UI + BFF, Docker |
| [Business-overview.md](Business-overview.md) | Product / all | Customer journey; what GP is and is not |
| [People-like-you-and-needs.md](People-like-you-and-needs.md) | Product / engineers | How People Like You, Need Profiler, and Need Calculator are called and calculated |
| [Calculations.md](Calculations.md) | Product / engineers | Formulas and data flow: PLU → profiler → calculator → plan → budget |
| [HU-and-SV-payloads.md](HU-and-SV-payloads.md) | Engineers | What the same session sends to HappiU vs Scenario Visualizer |
| [Risk.md](Risk.md) | Product / engineers | Risk capacity vs tolerance; mapping to net expected returns |
| [risk-mgmt.md](risk-mgmt.md) | Product / engineers | Risk product decisions and build sequence |
| [Architecture.md](Architecture.md) | Developers | Request flow, modules, prompts, upstreams |
| [API.md](API.md) | Developers | HTTP contract: predict / score / project / explain |
| [Testing.md](Testing.md) | Developers | Pytest (upstreams and OpenAI mocked) |
| [Open-issues-and-tasks.md](Open-issues-and-tasks.md) | Maintainers | Known gaps |
| [Standalone-third-party.md](Standalone-third-party.md) | Maintainers | GP-only GitHub repo; which FM/HU/SV APIs to open |

Root quickstart also lives in [`../README.md`](../README.md).

## Quickstart

```powershell
pip install -e ".[dev]"
python run_server.py          # http://127.0.0.1:8009

cd frontend
npm install
npm run dev                   # http://127.0.0.1:5179  (proxies /v1 → :8009)
```

Compose: service `gp` on host **8069** (WAN **8469**). Depends on `fm`, `hu`,
`sv`. Portal card: suite landing page.

## Status

Workspace D2C app (not a 360F engine migration). HTTP BFF + React journey are
live; engines stay in FM / HU / SV. Spoken explainers use OpenAI when
`OPENAI_API_KEY` is set, otherwise local scripts.
