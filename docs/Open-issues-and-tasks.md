# 360-Goal Planner — open issues and tasks

## Status

GP is a **D2C BFF + UI** (not a Falcon→FastAPI engine migration). The
five-step journey, FM/HU/SV mapping, and LLM explainers (with file prompts)
are in this repo. Engines stay remote — see
[Standalone-third-party.md](Standalone-third-party.md).

## Known gaps

| # | Item | Priority | Notes |
|---|------|----------|-------|
| 1 | Metrics / error envelope | Low | `/health` + `/healthz` only. No Prometheus `/metrics`, no canonical `{error, description}` envelope used by HU/PA/PG/SV. |
| 2 | Upstream default mismatch | Low | `FM_UPSTREAM` defaults to compose **8062**; HU/SV default to bare-metal **8002** / **8001**. Easy to hit the wrong FM when mixing compose and `run_server.py`. |
| 3 | SV tenant hardcoded | Med | `sv_project(..., tenant_id="helium")`. Fine for the demo; other tenants need a session field. |
| 4 | Human adviser | Low | Callback panel is local-only (“Nothing is sent from this prototype”). No CRM / ticket backend. |
| 5 | Prompt versioning | Low | Prompts are files in-repo; response `source` is `llm`/`fallback` with no prompt version header. |
| 6 | Frontend tests | Med | Typecheck only. No Playwright walk of the five screens. |
| 7 | Auth / persist | Med | Optional portal JWT hash handoff. `persist` on predict is wired but lightly used in the UI. |
| 8 | No GP numeric golden | Low | HU/SV goldens stay in those repos. GP does not re-assert engine numbers. |
| 9 | Document parse | Med | Statement upload is simulated / local in the UI; it is not FM’s holdings LLM pipeline. |
| 10 | Own git remote | Done | This repository is the GP-only GitHub remote. Operator notes: [Standalone-third-party.md](Standalone-third-party.md). |

## Deferred / nice-to-have

- Streaming Mira tokens instead of one utterance
- Caching identical explain contexts (cost control)
- Wire `planningCurrency` if the journey leaves Singapore dollars
- `/metrics` to match the operational trio on the engines
- Dedicated CI workflow once GP has its own remote

## Non-goals

- Reimplementing HappiU or Scenario Visualizer inside GP
- Selling or binding products
- Storing customer PII on the BFF (session lives in the browser)
