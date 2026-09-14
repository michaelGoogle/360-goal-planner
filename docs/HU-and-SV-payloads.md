# What GP sends to HappiU and Scenario Visualizer

GP never runs Monte Carlo. It maps the **same session** into two engine bodies:

| | HappiU (HU) | Scenario Visualizer (SV) |
|--|-------------|--------------------------|
| **GP route** | `POST /v1/score` | `POST /v1/project` |
| **Upstream** | `POST /v1/happi-u` | `POST /api/v2/scenario-visualizer?tenant_id=helium` |
| **Builder** | [`src/hu_payload.py`](../src/hu_payload.py) `build_happiu_payload` | [`src/sv_payload.py`](../src/sv_payload.py) `build_sv_payload` |
| **Answers** | `preHappiU` / `postHappiU` (utility score) | Year-by-year **gross assets**, cashflow, expense funding |
| **Sims** | `numSims` default **200** | `svNumSims` default **20** |

Need amounts are **not** recalculated here. Both engines receive the figures already stored on the session from `POST /v1/needs` ([Calculations.md](Calculations.md) §4).

Keep this page in lockstep with those two builders. If a mapping changes in code, change this page in the same commit.

---

## Same session, two jobs

Both payloads read:

- identity: `dateOfBirth` (or age → DOB), `gender`, `isSmoker`, `ageOfRetirement`
- money: `incomeMonthly`, `expenseMonthly`, `cash`, `investments`
- rates from [`src/session_rates.py`](../src/session_rates.py) (defaults 2.3% inflation, 1.2% cash, 2.8% income growth, 4.2% investment return)
- enabled UNIFIED needs, including `N_HOS`
- existing policies (cover / premium)

They **deliberately diverge** on property, mortgage, CPF, surplus saving, stress events, and the recommended plan. HU scores financial well-being. The Plan chart plots **gross assets** (cash, investments, home, CPF for citizens). Mortgage instalments leave cashflow; remaining principal is **not** subtracted from the stock.

---

## Side by side

| Input | HU | SV |
|-------|----|----|
| **Salary** | Gross **monthly**, `frequency: 1` | Gross **annual** (`incomeMonthly × 12`), `frequency: 2` |
| **Living spend** | `commonDetails.totalMonthlyRegularExpense` only (no expense rows) | Annual (`expenseMonthly × 12`), `PERSONAL_EXPENSE`, `frequency: 2` |
| **Cash** | `A_SAV`, session cash rate, contribution **0** | `A_SAV`, same rate, contribution **0** |
| **Investments** | `A_INV`, session investment return, contribution **0** | `INVESTMENT_PORTFOLIO`, same return, `recurringContribution` = **take-home − expense** (monthly leftover, no ×12 — SV treats the figure as a yearly add) |
| **Property** | **Not sent** | `RESIDENTIAL_PROPERTY` at session `property`, return = `assetReturn + 0.4%` (default 3.4%), illiquid |
| **Mortgage** | Empty loan stub (`currentValue: null`) | Loan stock + instalment: `currentValue`, 3.5%, 20 years, instalment = `mortgage / 20`. Remaining principal is subtracted from wealth (`subtractLoanBalances: true`) |
| **CPF** | `cpfSalaryContribution: true` unless `residency === Foreigner`. Balances not seeded. HU’s own CPF engine still runs for citizens. | `R_SGP` unless `residency === Foreigner` (`R_OTH`). OA/SA/MA/RA sent as 0; the CPF engine still accrues from salary |
| **Needs** | Enabled rows; **always includes `N_RET`** (synthesised if the customer turned it off) | Enabled rows; synthesises `N_RET` only if **no** needs at all |
| **Need codes** | GP `N_HOS` → HU `N_HSP` (`hu_need_code`) | Same rename, so SV sees `N_HSP` |
| **Existing cover** | Protection: policy sum assured. Wealth: cash + investments (or the row’s `existing`) | Protection: `existingInsurance[]` from session policies. Wealth existing is the cash/investment assets, not a tagged pot |
| **Tagged assets** | `{ id, type, partner: null }` placeholder | Protection needs tagged to the home id. Accumulation needs send `[]` |
| **Recommended plan** | `solutionOptimizerOutput.segregatedBudget` — one line per enabled need, placeholder premium / benefit | `benefitVisualizerOutput` only when Apply this plan has a mix (`planMth` / `planLump` / `planSum`). Omitted if every plan is off |
| **Stress events** | Off (`manualEvents.flag: false`) | Session `events` that are on → `manualEvents` (GP year 0 = SV year 1) |
| **Death flag** | `noDeathFlag: true` | `noDeathFlag: true` |
| **Currency** | SGD | SGD (via SV tenant; not a `commonDetails` block) |

Income is **gross** on both. Employee CPF is not stripped in the payload. HU and SV deduct it internally when the CPF flag / `R_SGP` is on.

---

## Person and rates

Shared:

- `dateOfBirth`, `gender`, `isSmoker`, `ageOfRetirement`
- inflation, income growth, cash interest, investment return from the assumption box

HU-only: `riskProfile` (suitable band 1–5), `numDependents`, `annualBudget: 1500`, `numSims` 200.

SV-only: `numSims` 20, `showExpenseFunding: true`, `ignoreIlliquidAssets: false`, `subtractLoanBalances: true`. Property return uses `assetReturn` (default 3%) + 0.4%.

---

## Cashflow

**HU** sends monthly gross salary as `I_SAL` with `frequency: 1` (monthly). Living costs sit on `commonDetails.totalMonthlyRegularExpense`; the `expenses` array is empty.

**SV** sends the same salary and spend as **annual** amounts with `frequency: 2`. That is the same money, not a second copy — HU and SV use different frequency enums (`1` = monthly, `2` = annual).

Take-home (`src/cpf.py` `session_take_home`) is used only for SV’s investment **contribution** (surplus). It is not the salary figure.

---

## Assets and debts

```text
SV chart = cash + investments + home + CPF (citizens) − remaining mortgage
         + surplus saving − plan premiums + plan pots (post path only)

HU score assets  = cash + investments
                 + HU CPF (citizens)
                 + HU’s own consumption / insurance math
```

| Stock | HU | SV chart |
|-------|----|----------|
| Cash | yes | yes |
| Investments | yes | yes, plus leftover take-home each year |
| Home | no | yes, full value, growing |
| Mortgage principal | no | yes, declining balance subtracted from wealth |
| Mortgage instalment | no | yes, cash out for 20 years |
| CPF balances | HU engine, not GP figures | SV CPF engine when `R_SGP` |
| Suggested plan | budget lines (score the mix) | BVO pots / cover (move the line) |

The Plan chart floors wealth at 0. The house stays on the line; only remaining mortgage principal is netted off.

---

## Needs

UNIFIED types: `N_INC`, `N_CRI`, `N_TPD`, `N_HOS`, `N_RET`, `N_EDU`, `N_SAV`, `N_PRP`.

Both builders:

1. Keep only `enabled` rows.
2. Rename `N_HOS` → `N_HSP` (HappiU’s hospitalisation code). Product code `HSP`.
3. Pass `needAmount` from the calculator as HU `totalNeed` / SV `capitalSumRequired`.

**HU `needCalculatorOutput`** is a map keyed by need code, with retirement living expenses (`expenseMonthly × lifestyleRate × 12`), CI medical cost placeholder S$62,400, hospitalisation `medicalCost` = the GP amount, life/TPD funeral S$10,000.

**SV `needCalculatorOutput`** is a **list** of `{ type, needId, result }`. Retirement gets `durationOfRetirement = 85 − retAge`. It does **not** send `expectedLivingExpenseInTheCountry`, so SV keeps today’s living spend after retirement (inflated).

HU always scores retirement. If the card is off, GP still appends an `N_RET` row so HappiU has a horizon.

Protection needs on SV (`N_INC`, `N_CRI`, `N_TPD`, `N_HOS`) are tagged to the home id so SV can sell that holding on death / CI / TPD. Hospitalisation tagging is currently a no-op in the engine (it only reacts to `N_INC` / `N_CRI` / `N_TPD` / `N_PAD`).

---

## Recommended plan

The D2C mix lives on the session (`planMth`, `planLump`, `planSum`, `planPrem`, `plansOff`).

- **HU** always sends a `segregatedBudget` line per enabled need (placeholder `budget` / rounded `benefitAmount`). That is what HU uses for **post** HappiU.
- **SV** sends `benefitVisualizerOutput` only for enabled needs that are not in `plansOff` and that have a non-zero monthly, lump, or sum assured. The post path is “with this plan”; the pre path is without those products.

Product codes match: `GPP` life, `CEJ` CI, `TPD` disability, `HSP` hospitalisation, `AIARS` retirement, `ERX` education, `SAV` savings, `PRP` property.

---

## Stress events (SV only)

HU’s `manualEvents` is a disabled stub. The Plan stress chips go to SV only.

GP slider year **0** is this year. SV columns are **1-based**, so GP offset `n` → SV year `n + 1`.

| GP id | SV `eventType` |
|-------|----------------|
| `crash` | `MarketCrash` |
| `ccy` | `CurrencyShock` (shock × 2/3, FX share of the book) |
| `infl` | `Inflation` |
| `inc` | `Income` (range, %) |
| `death` | `Death` |
| `ci` | `CI` |
| `tpd` | `PTD` |
| `pa` | `PersonalAccident` |
| `hosp` | `Hospitalization` |
| `care` | `Expense` (amount over a span) |
| `wed` | `Marriage` |
| `baby` | `Newborn` |
| `exp` | `Expense` (%) |

---

## What must stay in sync

When you change a mapping, update **both** builders unless the difference is listed above as intentional.

| Change | HU | SV |
|--------|----|----|
| New UNIFIED need | `PRODUCT_CODES`, `NEED_BASE`, `PROTECTION` / `ACCUMULATION`, `_calc_entry` | `_PLAN_PRODUCT`, need loop, BVO column |
| Hospitalisation code | keep `hu_need_code` (`N_HOS` → `N_HSP`) | import the same helper |
| Income / spend | still monthly + `frequency: 1` | still annual + `frequency: 2` |
| Session rates | `session_rate(...)` | same helper, same keys |
| Property on the chart | still omit | keep `RESIDENTIAL_PROPERTY`; tag protection needs to that id |
| CPF on the chart | `cpfSalaryContribution` unless Foreigner | same residency gate (`R_SGP` / `R_OTH`) |
| Mortgage on the chart | not required for the score | instalments plus `subtractLoanBalances` |

The score and the chart are different questions (HU never sends the home). Do not drop SV’s property tag without also dropping the house, or the id dangles.

Inspect live bodies: Plan **More…** / SV inspect, or `POST /v1/sv-payload`. Tests: `GP/tests/test_payloads.py`.

---

## Code index

| Concern | Path |
|---------|------|
| HU body | `src/hu_payload.py` |
| SV body + BVO + events | `src/sv_payload.py` |
| Shared need rename | `hu_need_code` |
| Take-home (SV surplus only) | `src/cpf.py` `session_take_home` |
| Rates | `src/session_rates.py` |
| Routes | `src/app.py` `/v1/score`, `/v1/project` |
| Chart series | `frontend/src/lib/sv.ts` (`floorWealth`) |
| Formulas for `needAmount` | [Calculations.md](Calculations.md) |
| HTTP envelopes | [API.md](API.md) |
