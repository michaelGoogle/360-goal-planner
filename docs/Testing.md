# 360-Goal Planner — testing

## Commands

```powershell
cd GP
pip install -e ".[dev]"
python -m pytest tests/ -q
python -m ruff check src tests
```

Frontend typecheck (no Jest suite yet):

```powershell
cd GP\frontend
npx tsc -b
```

No live LLM, HU, or SV is required for the default pytest suite —
People Like You completions and HU/SV are **mocked**. Profiler and calculator
run in-process.

Config: `pyproject.toml` → `testpaths = ["tests"]`, `pythonpath = ["."]`.

## What is covered

| Test | Intent |
|------|--------|
| `test_health` | `/healthz` returns `service: gp` |
| `test_parse_sentence.py` | Field normalize; no key → `unavailable`; mocked LLM JSON |
| `test_explain.py` | Prompt files load; fallback without key; mocked LLM; unknown kind **400** |
| `test_predict.py` | PLU down → **503**; mocked PLU + in-process profiler/calculator; assumed life cover |
| `test_pipeline.py` | Need Profiler scoring + Need Calculator amounts |
| `test_people_like_you.py` | Income clamp, anchors, CPF/spend (LLM mocked) |
| `test_payloads.py` | HappiU / SV bodies include needs, events, assumption rates |

## Manual checks

1. Start HU, SV, and GP (`run_server.py` or compose). Estimate does not need FM.
2. Vite UI on `:5179` — walk Start → About you → Your money → Your score → Your plan.
3. With `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`): speak a sentence on About you; tap Mira and “Explain
   these figures”. `/v1/explain` `source` should be `llm`.
4. Unset the LLM key and re-estimate: Estimate returns **503**.
5. Compose: `docker compose up -d gp` → http://127.0.0.1:8069/

## Out of scope

- Golden numeric HappiU / SV values through GP (those live in HU/SV test
  suites; GP only asserts payload shape)
- Exact spoken strings from OpenAI (non-determinism)
- Frontend component / Playwright tests
