# Calculations

How FinPlan360 turns a session into numbers. Start with
[Calculations.md](Calculations.md): the journey order, the shared inputs
(Assumptions, CPF, need parameters, risk, stress events), and which session
attributes each component reads and writes.

Each other file is the algebra for one component. If a formula and
`Calculations.md` disagree, the formula file is the source of truth.

| File | What you get |
|------|----------------|
| [Calculations.md](Calculations.md) | Logic flow, shared assumptions, attribute map, code index, open issues |
| [Need-dictionary.md](Need-dictionary.md) | One section per need: what it covers, risk, calculator, parameters, labels in every module |
| [Dictionary.md](Dictionary.md) | One code per need (N_), risk (R_) and parameter prefix; parked and dropped needs |
| [Currency.md](Currency.md) | USD system currency: convert in, calculate, convert back; fixed amounts; country plug-ins |
| [CHANGELOG.md](CHANGELOG.md) | Model changes by version and whether the code follows |
| [People-like-you.md](People-like-you.md) | Income (LLM, then clamped), expenses, assets, liabilities |
| [Need-profiler.md](Need-profiler.md) | Weighted scores → which UNIFIED needs are on, and their priority |
| [Need-calculator.md](Need-calculator.md) | `needAmount`, projected have, and gap for each need type |
| [Goal-cards.md](Goal-cards.md) | How Score and Plan write slider edits back through `POST /v1/needs` |
| [Plan-calculator.md](Plan-calculator.md) | Suggested sums, premiums, lumps, and monthly contributions |
| [Budget-calculator.md](Budget-calculator.md) | Half of monthly surplus vs plan premiums and contributions |
| [HappiU.md](HappiU.md) | What GP sends to HU, and how pre/post HappiU is scored |
| [Scenario-visualizer.md](Scenario-visualizer.md) | What GP sends to SV, and how the year-by-year wealth path is built |

People Like You, Need Profiler, Need Calculator, Plan and Budget run inside GP.
HappiU and Scenario Visualizer are scored and projected by HU and SV; the files
here describe the payload GP builds and the principle of the result.

Related docs outside this folder: [People-like-you-and-needs.md](../People-like-you-and-needs.md),
[HU-and-SV-payloads.md](../HU-and-SV-payloads.md), [Risk.md](../Risk.md).

## Versions and change log

This folder is the live model from V0-14 on (promoted from `calculations_clone`
at V0-25). V0-13 and earlier live in [`docs/Archive/calculations/`](../Archive/calculations/README.md).
Workbook snapshots V0-14–V0-24 sit in [`Archive/`](Archive/). For a new tree, clone
this folder to a sibling at the same depth under `docs/` so the build script still
finds `src/` and `../HU`. For every model change, bump `OUT` in
`build_calculations_workbook.py` first.

Workflow: change the **Excel first**, then these docs, then the code. Every
change gets a row in [CHANGELOG.md](CHANGELOG.md) and in the workbook's
**Change log** tab (same rows, kept in `CHANGELOG` in the build script). The
code-status column says whether the code already follows.

## Workbook

[Calculations V0-25.xlsx](Calculations%20V0-25.xlsx) is the current live model
of the closed-form engines, plus deterministic one-path copies of Scenario
Visualizer and HappiU. The **Discrepancies** tab is empty as of V0-25 (code
follows V0-24; parked ideas live in Calculations.md).

Pick the persona on the **Selected persona** tab. Every later tab follows
that id. Each of those tabs is split into marked blocks:

- **A · input** (gold/yellow) — attributes from the selected Personas row, or
  results of the previous component used as this component’s inputs
- **B · LLM predicted** (blue) — prompt fields this component actually reads
- **D · assumptions / shared** (purple) — named cells from the Assumptions tab
- **C · calculated** (green) — this component’s deterministic results
- Orange cells are overrides (blank keeps the calculated value)

| Tab | What it is |
|-----|------------|
| Dictionary | Needs, risks and parameter names (generated with Dictionary.md) |
| Overview | The eight components, owner, reads / writes, and the live formula |
| Selected persona | The only dropdown. About you, LLM flags, and the effective session for that id |
| Personas | All 50 rows: **A input** · **B LLM predicted** (J–V, editable) · **E Money-page overrides** (expense, cash, investments, property, mortgage, liabilities, life sum) |
| CPF | Social-security plug-in. SG-CPF module or the default (no contribution, take-home = income). Orange override. |
| People Like You | Selected persona: inputs, assumptions, calculated, overrides, then **effective** session values. Reads take-home from CPF. |
| FX | 152 currencies and a PPP table for 245 countries (data in `fx_ppp/`). USD per 1 user-currency unit (#N/A if unknown), relative price level (option B, base Singapore), PPP-USD, USD session amounts, rounding steps in user currency |
| Validation | USD-only min/max on the FX amounts (local currency is unchanged) |
| Need Profiler | Selected persona: inputs, assumptions, option weights and scores; orange Enable? |
| Need Calculator | Selected persona: inputs, sliders, S-block (USD inputs), then amount / have / gap in USD (H–J) and user currency (B–D) |
| Plan Calculator | Selected persona: suggested sums, premiums, monthly contributions; orange Include? |
| Budget Calculator | Selected persona: take-home surplus vs the included plan |
| Scenario Visualizer | Selected persona: one deterministic SV path. Mortgage is a 20-year annuity at `loanRate`; wealth (chart line) and spendable wealth (expense-funding panel), pre and post |
| HappiU | Selected persona: deterministic twin of the HappiU score |
| Assumptions | Shared rates, CPF, need parameters, profiler weights, stress catalogue |
| Discrepancies | Empty as of V0-25: the code follows V0-24. Parked ideas are in Calculations.md |
| Change log | Model changes by version, and whether the code already follows |
| Code check | Snapshot from the GP modules at build time (does not follow edits) |

The build script also needs the HU folder beside GP (`SiriHeritage/HU`) for
the HappiU mortality / morbidity tables. `excel_check.py` (Windows + Excel)
compares the SV and HappiU tabs with the Python twins in
`deterministic_engines.py`.

Regenerate after a code change:

```powershell
python docs\calculations\build_calculations_workbook.py
```
