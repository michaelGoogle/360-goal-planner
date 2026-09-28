# Parity fixtures — calculation model V0-24

Expected results exported from `docs/calculations/Archive/Calculations V0-24.xlsx` (LibreOffice
recalculation) by `docs/calculations/export_fixtures.py`. The code must reproduce these
numbers (Implementation-plan.md, WP0 and §6). Do not edit by hand; re-export for a new model
version into a new folder (`model_v0_25/`, …).

| File | Content |
|------|---------|
| `parameters.json` | Every named cell on the Assumptions tab: value, cell, label, unit, currency, status, code source, changed in, open proposal. Seed for the admin parameters `v24.json` (WP2). |
| `personas/P01.json … P50.json` | One file per persona (default session, no overrides). |
| `scenarios/P03_VND_Vietnam.json` | P03 as a Vietnamese customer at the same USD income (PPP, price level 0.46). |
| `scenarios/P03_PAC_LTC_on.json` | P03 with N_PAC and N_LTC switched on (Enable? = TRUE). |
| `scenarios/P03_all_stress_events.json` | P03 with every personal stress event and R_LON on (Scenario Visualizer). |
| `index.json` | Case list and formula-error count (all 0). |

Each case file:

| Key | From workbook | Use in tests |
|-----|---------------|--------------|
| `inputs` | Personas row (About you + LLM predicted) | Service inputs (LLM values taken from here, not re-generated) |
| `edits` | Cells changed for the scenario | Scenario set-up |
| `fx.values` | `FX_*` named cells (rate, price level, PPP-USD, USD session amounts, rounding steps) | FX lock / money helpers (WP3) |
| `cpf.values` | `CPF_*` | Social-security service (WP4) |
| `peopleLikeYou.values` | `PLU_*` effective session | People Like You (WP5) |
| `needProfiler.values` / `raw` / `scaled` / `optionWeights` | `NP_*`, raw and scaled label scores, option weights | Need Profiler (WP7) |
| `needCalculator.values` / `rows` | `NC_*` (amount / have / gap / on, USD columns, horizons, R_LON), all labelled rows | Need Calculator (WP8) |
| `plan.values` / `rows` | `PLAN_*`, all labelled rows (caps, shares, premiums) | Premium mock and Plan (WP9, WP10) |
| `budget.values` | Budget Calculator labelled rows | Budget (WP11) |
| `happiU.values` / `years` | `HU_*` payload fields and deterministic twin results | HappiU payload (WP12) |
| `scenarioVisualizer.values` / `years` | `SV_*` payload fields and year-by-year path (`SV_Y_*`) | SV payload and stress events (WP13) |
| `formulaErrors` | Any #REF / #VALUE / … in the recalculated workbook | Must be empty |

Money is in the user currency (SGD for all personas, VND in the VND scenario) unless the key
says USD. The FX snapshot is 2026-09-25 (SGD 0.78162734): run parity tests with
`GP_SVC_FX=snapshot`.

Tolerances (plan §6): user-currency amounts exact (±1 where Python and Excel round halves
differently); rates 1e-9; HappiU score ±1; SV path ±0.05 %.

Re-export:

```powershell
cd GP\docs\calculations
python export_fixtures.py                       # all personas and scenarios (needs LibreOffice)
python export_fixtures.py --only P03,P06        # a few
```
