# Change log — calculation model

Newest first. Same rows as the **Change log** tab in the workbook
(`CHANGELOG` in `build_calculations_workbook.py`). Workflow: Excel → docs →
code. **Code status** says whether the code already follows the model.

## V0-26 — 2026-09-28

| Item | Change | Where | Code status |
|------|--------|-------|-------------|
| Horizons | `N_SAV` / `N_PRP` default years are `max(5, 40 − age)` and `max(3, 33 − age)`. Education still aims at next year once past 50. Under 30 / 35 nothing changes. | Need Calculator target years; `session-defaults`; Need Calculator service | In code |

## V0-25 — 2026-09-28

Code follows V0-24 (WP0–WP15).

| Item | Change | Where | Code status |
|------|--------|-------|-------------|
| Follow-through | GP calculators, FX lock, PPP, N_PAC / N_LTC, plan / budget BFF, HappiU and SV payloads, and the frontend spend floor (USD 100 via FxLock) now follow V0-24. | whole tree | In code |
| Need Profiler twins | Leftover pipeline no longer swaps N_SAV for N_PRP. Workbook twins call the live Need Profiler (`src/services/need_profiler`). | `select_unified_top`; `twin_profiler` | In code |
| Discrepancies | Tab empty. Parked (not in this model): real premium API, wiring policies into profiler Existing*Coverage, unifying HU/SV CPF with GP. | Discrepancies; Calculations.md Open issues | — |

Check: HappiU scores match the twins for the personas run (`excel_check.py`). SV wealth and spendable match after the plan twin calls the live Plan Calculator; `savPost` can still differ as a savings-vs-plan-pot split while those totals agree. Parked ideas are in Calculations.md, not on Discrepancies.

## V0-24 — 2026-09-27

Pre-code clean-up. After this version the Discrepancies tab lists only code changes.

| Item | Change | Where | Code status |
|------|--------|-------|-------------|
| A1 | Money-page overrides (Personas W–AC) cleared for all 50 personas: every tab now shows People Like You calculated values. | Personas | — |
| A2 | Plan default monthly contribution = (free budget − protection premiums / 12) ÷ n wealth, rounded **down** to the step. Free budget = 50% of monthly surplus, as in the Budget Calculator, so the default plan always fits (P06: 1,719 over 1,693 → 1,620 under 1,693). | Plan Calculator | In code (`src/services/plan`) |
| A3 | Goal target years by age: N_EDU at `EDU_TARGET_AGE` 50, N_SAV at `SAV_TARGET_AGE` 40, N_PRP at `PRP_TARGET_AGE` 33 (next year if already older). Each goal has its own horizon in the Need Calculator, Plan, Scenario Visualizer (withdrawals, pots) and HappiU. `EDU_YEARS_DEFAULT` removed. | Assumptions rows 18, 19, 40; Need Calculator; Plan; SV; HappiU | In code |
| A4 | People Like You vocabulary mapped to profiler options: Basic / Comfortable / Luxurious → frugal / stress-free / only the best; Single → A, Double / Ward → B; adventurous sports → 4, none → 0, other sports → 1. | Need Profiler | In code |
| A6 | USD fixed amounts recalibrated at the SGD rate of the FX snapshot (0.7816), so Singapore amounts are unchanged in SGD (CRI_COST S$200,000 again). LTC_COST (USD 129,000) and MIN_EXPENSE_MONTHLY (USD 100) were set in USD and stay. | Assumptions, stress table | In code |
| A7 | Discrepancies tab rewritten as the code implementation backlog (14 rows). Model decisions and parked ideas live in the Change log and Calculations.md. | Discrepancies | — |
| A8 | Docs brought in line with the recalibrated amounts of A6: the fixed-amount table in `Currency.md`, the need parameters, stress sizes, home-seed bands, rounding steps and HappiU envelope in `Calculations.md`, and the constants in `Need-calculator.md`, `People-like-you.md`, `HappiU.md`. `Need-profiler.md` now says the profiler scores in PPP-USD (V0-22/23), not market USD. `Need-dictionary.md` and its source in the build script name `CRI_COST` / `TPD_COST` / `PAC_COST` instead of repeating their values, so they cannot drift from Assumptions again. The V0-22 VND check was re-run on the V0-24 fixture. | docs | — |

Check (LibreOffice): no formula errors. P03: horizons N_EDU 16, N_SAV 6, N_PRP 1 years; N_CRI 452,382 (S$ amounts as before V0-22); plan 700 / month against a free budget of 785. P06: plan 1,620 against 1,693. Profiler picks unchanged for P01, P03, P06, P26, P40; P12 moves from N_INC to N_CRI (lifestyle / ward now score), HappiU 35 → 29.

## V0-23 — 2026-09-27

| Component | Change | Where | Code status |
|-----------|--------|-------|-------------|
| Need Profiler | Section D row "USD per 1 local" replaced by "PPP-USD per 1 local (market ÷ price level)" `=FX_pppUsdPerLocal`, the rate the profiler's USD rows use since V0-22. Display only; no result changes. | Need Profiler D-block | — |

## V0-22 — 2026-09-26

| Component | Change | Where | Code status |
|-----------|--------|-------|-------------|
| FX | Rate table 9 → 152 currencies, market rate of 2026-09-25 (`fx_ppp/currencies_fx.csv`). | FX tab I:L | In code (`GP_SVC_FX=snapshot` / FM) |
| PPP | New PPP table for 245 countries: World Bank PPP, 2024 average market rate, price level (US = 1); 186 usable. Price level per country, relative to `PPP_BASE_COUNTRY` Singapore. Option B switched on (`priceLevelOn` TRUE, `fxMode` B): USD fixed amounts × relative price level; Need Profiler bands compare PPP-USD. Country without usable PPP → market rate. | FX tab N:U and D-block; Assumptions rows 23, 24, 78; Need Profiler | In code |
| Rate update | SGD 0.74 → 0.7816. USD fixed amounts unchanged, so Singapore amounts in SGD fall 5.3% (P03: N_CRI 452,382 → 441,730, N_EDU 94,149 → 89,135). Rounding steps unchanged (nice steps). | all | — |

Check (LibreOffice): no formula errors. Singapore: price level factor 1, profiler picks and HappiU (87) unchanged. P03 as a Vietnamese persona at the same USD value: factor 0.46; N_INC equal to the SGD result, N_CRI / N_EDU / N_LTC at 46% of the Singapore amounts. See Currency.md.

## V0-21 — 2026-09-26

| Component | Change | Where | Code status |
|-----------|--------|-------|-------------|
| Assumptions | Parameter review merged: every row now has unit, currency, status, code source, changed in, open proposal. Income bands moved to J4:M13, stress events to a named table (J19), plus a list of parameters that stay on other tabs by design. Parameter review tab removed. | Assumptions | — |
| Life expectancy | One default (`lifeExpectancyDefault` 85) and one cap (`LON_AGE` 99). GP sends them: HappiU default 83 → 85; SV path end 100 → 99; chart horizon = session life expectancy (was fixed 85). | People Like You, HappiU, Scenario Visualizer | In code |
| HappiU | GP sends `CRI_COST` and `TPD_COST` (USD → user currency) as HappiU's medical costs; were HU 200,000 / 444,000. `CRI_MEDICAL_HU` merged into `CRI_COST`. | HappiU, Assumptions | In code |
| Spend floor | `MIN_EXPENSE_MONTHLY` USD 100 (was S$100), applied to effective `expenseMonthly`. | Assumptions, People Like You | In code |
| Stress events | Sizes in USD (`R_xxx_SIZE`), personal risks by age (`R_xxx_WHEN`): R_DEA 14,800 at 60; R_CRI = CRI_COST at 55; R_TPD = TPD_COST at 50; R_PAC = PAC_COST at 45; R_HOS 88,800 at 50; R_LTC = LTC_COST a year from LTC start age to life expectancy; R_WED 44,400 year 5; R_BAB 25,900 year 3. Scenario Visualizer applies them when switched on (new "stress events cost" column; death stops salary and CPF wage). | Assumptions, Scenario Visualizer | In code |
| Twins | `deterministic_engines.py`: SV path to 99, HU default LE 85, HU TPD cost 200,000 SGD. | build folder | — |

Check (LibreOffice, P03): no formula errors. Changes vs V0-19 are only the decided ones: HappiU pre-score raw 0.8661 → 0.8662 (score 87 unchanged), SV path 66 → 65 years, chart horizon 85 → 88. With every personal event on, costs land at ages 38, 40, 45, 50, 55, 60 and 80–87; salary stops at 60.

## V0-20 — 2026-09-26

| Component | Change | Where | Code status |
|-----------|--------|-------|-------------|
| Parameter review | New tab listing 58 parameters: every fixed amount, age and timing, with current value, unit, currency, status (USD done · SGD → convert · Year offset → age · Harmonise · Local by design · No currency) and a proposal. Decision column for review. No formula changed. | Parameter review tab | — |

## V0-19 — 2026-09-26

| Component | Change | Where | Code status |
|-----------|--------|-------|-------------|
| N_LTC | New protection calculator, long-term care: annuity-due (at `realReturn`) of `LTC_COST` USD 129,000 a year (nursing home) over care years = life expectancy − LTC start age. Start age default 80 (`LTC_START_AGE`), a front-end input on the Need Calculator. Have = 0. Plan sizes it like other protection; Budget and Scenario Visualizer include its premium. The profiler never switches it on (no label). R_LON block shows `N_LTC` with care until 99. `R_LTC` linked to `N_LTC`. | Assumptions rows 25–26; Need Calculator; Plan; Budget; Scenario Visualizer; Dictionary | In code (GP/SV); HappiU has no LTC |
| Decision | R_LON stays display-only: the plan is not re-sized to 99. | — | — |
| Discrepancies | Row 14: N_LTC not in code / HappiU; no social-scheme offset (e.g. CareShield Life); R_LTC stress size (S$90,000 a year) not linked to `LTC_COST`. | Discrepancies | — |

Check (LibreOffice): no formula errors; P03 every V0-18 value unchanged with N_LTC
off. P03 with N_LTC on: 8 care years (88 − 80), need 1,308,765 SGD
(USD 968,486), premium 1,020 a year; at 99: 19 care years, 2,820,893.

## V0-18 — 2026-09-26

| Component | Change | Where | Code status |
|-----------|--------|-------|-------------|
| Naming | **TPD** is the one name for total & permanent disability: profiler label, weight matrix, HappiU tab, Dictionary. The JSON key stays `disability` and the HU engine still says PTD (Discrepancies 13). | Need Profiler, Assumptions, HappiU, Dictionary | Not in code |
| N_PAC | Agreed: 1 year of income replacement (annuity-due) + `PAC_COST` USD 59,200. "Proposal" removed. | Assumptions, Need Calculator | In code (GP sends N_PAC when enabled) |
| R_LON | New longevity stress event: `LON_AGE` 99. Need Calculator shows `N_RET` need, gap and extra need at 99. Scenario Visualizer toggle `R_LON` moves the chart horizon to 99 and reports wealth and spendable wealth there. The plan is not re-sized. | Assumptions `LON_AGE` and stress table; Need Calculator R_LON block; Scenario Visualizer | In code |

Check (LibreOffice): no formula errors; P03 every V0-16 value unchanged. R_LON for
P03: `N_RET` 1,633,487 → 2,201,580 at 99; spendable wealth with the plan
1,480,189 at 85, 1,189,524 at 99.

## V0-17 — 2026-09-26

| Component | Change | Where | Code status |
|-----------|--------|-------|-------------|
| Dictionary | Accidental death `N_ADB` (risk `R_ADB`) added as a protection candidate: the HappiU engine already scores it like `N_INC`; no GP calculator or profiler label yet. `N_PAC` noted as supported by the HappiU engine (GP does not send it yet). | Dictionary tab; Dictionary.md | Not in code |
| Docs | New [Need-dictionary.md](Need-dictionary.md): one section per need, generated by the build script from the Dictionary data. | this folder | — |

## V0-16 — 2026-09-26

Needs, risks and parameters get one naming scheme. Dictionary:
[Dictionary.md](Dictionary.md) and the **Dictionary** tab.

| Component | Change | Where | Code status |
|-----------|--------|-------|-------------|
| Dictionary | One code per need (`N_`), risk (`R_`) and parameter prefix. Parameters renamed: `CI_COST`/`CI_YEARS` → `CRI_*`, `HOSP_MONTHS` → `HOS_MONTHS`, `EDU_TOTAL_COST` → `EDU_COST`, `eduYearsDefault` → `EDU_YEARS_DEFAULT`, `lifeSupport*` → `INC_SUPPORT_*`, `lifestyle*` → `RET_LIFESTYLE_*`, `sav/prpIncomeMultiple` → `SAV/PRP_INCOME_MULT`, `criMedicalPlaceholder` → `CRI_MEDICAL_HU`. Stress events carry `R_` codes (`R_DEA` death ↔ `N_INC`, `R_CRI`, `R_TPD`, `R_HOS`, `R_PAC`, `R_LTC`, `R_MKT`, `R_CCY`, `R_INF`, `R_ICT`, `R_EXP`, `R_WED`, `R_BAB`). | Dictionary tab; Assumptions; Scenario Visualizer event labels | Not in code |
| Need Profiler | Farewell dropped (scaling over 11 labels). `N_HOM` / `N_CAR` / `N_TRV` parked (scored, priority, no calculator). `N_PAC` joins the protection pick. Growth pick `N_EDU` vs `N_SAV`; SAV ↔ PRP swap removed; `N_PRP` (home purchase) never auto-picked. Fixed: `N_RET` / `N_PRP` flags were text "TRUE" / "FALSE", now real booleans. | Need Profiler; Assumptions weight matrix | Not in code |
| Need Calculator / Plan / Budget / SV | New calculator `N_PAC` (proposal: 1 year of income + USD 59,200). Plan sizes it, Budget and SV include its premium; HappiU does not receive it. Funeral lump removed. | Need Calculator, Plan, Budget, Scenario Visualizer | Not in code |
| Discrepancies | New rows 10 (`N_PAC` proposal), 11 (`N_PRP` has no profiler label), 12 (code still uses old names). | Discrepancies | — |

Check (LibreOffice recalculation): no formula errors for P01, P03, P06, P26.
Needs and amounts are unchanged except where the profiler pick changed: owners
P03, P06 and P26 had `N_PRP` (home purchase) switched on by the old swap and now
get `N_SAV`, which also moves the Scenario Visualizer path (goal withdrawal).
`N_PAC` switched on for P03: need 165,680, premium 130, included in Budget and SV.

## V0-15 — 2026-09-25

USD becomes the system currency (option A: market rate). Design:
[Currency.md](Currency.md).

| Component | Change | Where | Code status |
|-----------|--------|-------|-------------|
| All | Every fixed money amount is USD (= V0-14 SGD value × 0.74, so Singapore is unchanged): CI / TPD / EDU costs, home-seed values and income bands, life-cover / lump / monthly / premium / HappiU-benefit steps, premium floor, HappiU envelope, funeral lump. `systemCurrency`, `fxMode`, `priceLevelOn` added. | Assumptions rows 21–24 and the USD rows | Not in code (`goal_math.py`, `predict.py`, `planProducts.ts`, `hu_payload.py` still SGD) |
| FX | Unknown currency → `#N/A` (no SGD fallback). Price-level column for option B (1, switch off). Rounding steps in user currency: USD step ÷ rate → nearest 1 / 2 / 5 × 10^k. | FX tab | Not in code (`src/fx.py` falls back to SGD; no session lock) |
| Need Calculator | Runs in USD: S-block converts every money input, amount / have / gap in USD (H–J), back to user currency and rounded (B–D). | Need Calculator | Not in code |
| People Like You | Home seed on USD bands and USD values, converted back. Life cover rounds to the life-cover step in user currency. | People Like You | Not in code |
| Plan / HappiU | Contribution and premium steps, HappiU benefit step in user currency (SGD 50 / 10 / 50,000). Budget Calculator is ratios only, unchanged. | Plan Calculator; HappiU | Not in code |
| CPF | Framed as a social-security plug-in: SG-CPF module or the default (no contribution). | CPF tab | `src/cpf.py` only; HU and SV run their own CPF |
| Discrepancies | Rows 1 and 6 rewritten; new rows 7 (FX feed and session lock), 8 (HU / SV engine constants), 9 (price level option B). | Discrepancies | — |
| Docs | New `Currency.md`. Updated `Calculations.md` §3, `Need-calculator.md`, `People-like-you.md`, `Plan-calculator.md`, `HappiU.md`, `README.md`. | this folder | — |

Check: Singapore personas P01, P03, P06, P09, P12, P23, P26, P48 give the
same value as V0-14 on every named cell (LibreOffice recalculation), no
formula errors. P03 re-entered in VND at the same USD value gives the SGD
result × rate on every need; V0-14 gave N_CRI 4,914,999,141 VND instead of
8,809,535,983 and N_EDU 94,149 VND instead of 1,833,435,869.

## V0-14 — 2026-09-25

Folder: `docs/calculations_clone/` (cloned from `docs/calculations/`, V0-13; first created as `calculations-V0-14`, renamed).

| Component | Change | Where | Code status |
|-----------|--------|-------|-------------|
| Scenario Visualizer | Mortgage instalment is a level 20-year annuity at `loanRate`: `mortgage × r / (1 − (1 + r)^−20)`, rate 0 → `mortgage / 20`. Replaces `round(mortgage / 20)`. The balance now runs smoothly to 0 in year 20; no step at the end of the term. | SV tab `SV_inst`, mortgage balance column; `deterministic_engines.py` `twin_sv`, `annual_loan_payment` | In code: `goal_math.annual_loan_payment`, `sv_payload.py`. Workbook caught up. |
| Scenario Visualizer | New spendable-wealth columns for the expense-funding panel: cash + investments + savings (+ plan pots on post) − max(0, remaining mortgage − (home + CPF)). Not floored. New results: first age spendable wealth < 0, pre and post. | SV tab `SPENDABLE pre/post`, `SV_spOutPre`, `SV_spOutPost`; `twin_sv` `spendable`; `excel_check.py` `SV_COLS` | In the SV engine (`CashFlowGeneratorV2` `spendableWealth`). Open: earmarked goal pots funded from assets are 0 in the workbook. |
| Docs | `README.md`: folder-per-version rule, Change log, SV and HappiU tab rows. `Scenario-visualizer.md`: pointer to the workbook columns. | this folder | — |
| Tooling | `excel_check.py` imports without pywin32, so the twins can be checked on machines without Excel. | `excel_check.py` | — |

Check: the SV tab was recalculated (LibreOffice) for P01, P03 and P06 and
matches the Python twin on every checked column (wealth, CPF, savings,
spendable). P03 (S$192,500 at 3.5%): instalment S$13,545 a year, balance
S$13,073 in year 19 and 0 in year 20.
