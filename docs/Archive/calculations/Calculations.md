# 360-Goal Planner — calculations and data flow

This document is the **logic flow** for FinPlan360, then one level of detail
on each calculation component: which session attributes it reads and writes,
and how the calculation works in principle. Algebra for each component lives
in this folder. If a formula and this page drift, the formula file is the
source of truth.

The product story stays in [Business-overview.md](../Business-overview.md). HTTP
and modules stay in [Architecture.md](../Architecture.md) and [API.md](../API.md).
How risk ability is calculated from the balance sheet is in [Risk.md](../Risk.md).
The shared risk attributes themselves are in §3. Field-by-field HappiU and
Scenario Visualizer bodies are in [HU-and-SV-payloads.md](../HU-and-SV-payloads.md).

Names below are the session attribute names (`incomeMonthly`, `needAmount`,
`inflationRate`, …). The same name means the same field in every component.

---

## 1. Logic flow

Five inputs are shared. They are not steps in the customer journey. Every
component that needs one of them reads that same set.

| Shared input | What it holds |
|--------------|----------------|
| Assumptions | Economic rates and life-cycle settings |
| CPF | Black box. Gross pay in; employee CPF and take-home out |
| Need parameters | Years, lumps, and multiples behind each UNIFIED need |
| Risk | Risk ability and risk tolerance, combined into `riskProfile` |
| Stress events | Default shocks Scenario Visualizer applies when a chip is on |

The journey writes one session. Each component reads that session, plus the
shared inputs it needs, and adds its own attributes.

Income, expenses, savings, investments, and policies are session attributes.
People Like You fills them, or the customer edits the same fields. That edit
has no calculation of its own. Need Calculator follows those attributes.

```text
Shared inputs
    Assumptions · CPF · Need parameters · Risk
         │
         ▼
About you
    │  age, gender, residency, occupation, dependents
    ▼
People Like You                    reads CPF
    │  or the customer edits the same attributes (no calculation of their own)
    │  incomeMonthly, expenseMonthly, cash, investments, policies,
    │  property, mortgage, lifeExpectancy, isSmoker
    ▼
Need Profiler
    │  needs[].enabled, needs[].priority
    ▼
Need Calculator                    reads those money attributes, Assumptions, Need parameters
    │  needs[].needAmount, needs[].have, needs[].gap
    ▼
HappiU                             before a plan exists
    │  reads Assumptions, CPF, Need parameters, riskProfile
    │  preHappiU, postHappiU
    ▼
Plan Calculator                    reads Assumptions; investmentReturn follows riskProfile
    │  planSum, planPrem, planMth, planLump, plansOff
    ▼
Budget Calculator                  reads the plan; does not change needs or the plan
    │  monthly surplus vs premiums + contributions
    ▼
Scenario Visualizer                with plan; reads Assumptions, CPF
    │  year-by-year wealth path
    ▼
HappiU                             with plan (same score call, plan attributes set)
       preHappiU, postHappiU
```

`POST /v1/predict` runs People Like You, Need Profiler, and Need Calculator
in one call. `POST /v1/needs` reruns Need Calculator only. `POST /v1/score`
is HappiU. `POST /v1/project` is Scenario Visualizer. Plan Calculator and
Budget Calculator run in the UI (`seedProducts`, `planProducts.ts`). The
sequence diagram is in [Architecture.md](../Architecture.md#journey-sequence).

HappiU returns both `preHappiU` and `postHappiU` on every score call.
`postHappiU` is HappiU’s own with-recommendation score (the recommendation is the plans from Plan Calculator). The second score
call is the one that also carries the Goal Planner plan (`planSum`,
`planPrem`, `planMth`, `planLump`). Scenario Visualizer runs on that same
plan session. There is no chart call before Plan.

UNIFIED need types, in order: `N_INC`, `N_CRI`, `N_TPD`, `N_HOS`, `N_RET`,
`N_EDU`, `N_SAV`, `N_PRP`. Protection types are the first four. Wealth types
are the last four.

| Component | Owner | Code |
|-----------|--------|------|
| Assumptions | Session | `src/session_rates.py`, `frontend/src/lib/assumptions.ts` |
| CPF | Shared black box | `src/cpf.py` today; HU and SV still deduct with their own engines |
| Need parameters | Shared | `src/pipeline/goal_math.py` |
| Risk | Shared | `frontend/src/lib/riskCapacity.ts` ([Risk.md](../Risk.md)) |
| People Like You | GP pipeline | `src/pipeline/people_like_you.py`, `src/predict.py` `_apply_plu` |
| Need Profiler | GP pipeline | `src/pipeline/need_profiler.py` |
| Need Calculator | GP pipeline | `src/pipeline/need_calculator.py` `evaluate_session` |
| HappiU | HU, via GP | `src/hu_payload.py` → `POST /v1/score` |
| Plan Calculator | GP UI | `frontend/src/lib/planProducts.ts`, `local.ts` `seedProducts` |
| Budget Calculator | GP UI | `planAfford` in `planProducts.ts` |
| Scenario Visualizer | SV, via GP | `src/sv_payload.py` → `POST /v1/project` |

---

## 2. Assumptions

Standalone shared component. Defaults match the assumption box
(`ASSUME_DEFAULTS`). A missing session value falls back to the same default
in `session_rate`.

| Attribute | Default | Meaning |
|-----------|---------|---------|
| `inflationRate` | 2.3% | Price inflation |
| `interestRate` | 1.2% | Growth on `cash` |
| `loanRate` | 3.5% | Mortgage interest, for the loan payment and the chart |
| `incomeGrowthRate` | 2.8% | Growth of `incomeMonthly` over the projection |
| `investmentReturn` | 4.2% | Net expected return after product costs. Grows `investments` and discounts needs |
| `assetReturn` | 3.0% | Growth on `property` |

Two life-cycle attributes sit beside the rates. They are shared the same way,
and they are only partly on the assumption box today.

| Attribute | Default | Meaning |
|-----------|---------|---------|
| `ageOfRetirement` | 65 | Retirement age. Need Calculator, Plan Calculator, HappiU, and Scenario Visualizer all read it |
| `lifeExpectancy` | 85 | Years of life, **capped at 99**. People Like You may overwrite it. Need Calculator and HappiU use `lifeExpectancy − ageOfRetirement`. Missing or ≤ 0 → 85. The chart horizon is the separate session field `endAge` (also 85) |

**Real return** is derived, not stored:

```
realReturn = max(0, (1 + investmentReturn) / (1 + inflationRate) − 1)
```

Need Calculator and Plan Calculator discount future money at `realReturn`. HappiU and
Scenario Visualizer receive the nominal rates and apply them inside their
own simulations.

**Who writes `investmentReturn`.** The assumption box writes it. Until the
customer touches the rate, Risk writes it too: `riskProfile` seeds the
default. See Risk in §3.

**Who reads which rate today.** The rule is that every component reads
Assumptions. The code does not do that yet.

| Component | Rates it reads today |
|-----------|----------------------|
| People Like You | None. Take-home comes from the CPF black box; the household parameters in §3 set the rest |
| Need Profiler | None |
| Need Calculator | `inflationRate`, `investmentReturn`, `lifeExpectancy`, `ageOfRetirement` |
| HappiU | `inflationRate`, `incomeGrowthRate`, `interestRate`, `investmentReturn`, `ageOfRetirement`, `lifeExpectancy` |
| Plan Calculator | `inflationRate`, `investmentReturn`, `ageOfRetirement` |
| Budget Calculator | None of the rates. It compares surplus with the plan |
| Scenario Visualizer | All six rates, plus `ageOfRetirement` and `endAge` |

---

## 3. Other shared data

These sit beside Assumptions. A change belongs in one place, and every
reader uses that place. CPF, Need parameters, Risk, and Stress events are
part of this shared set.

### CPF

Black box. The rates, the wage ceiling, and the age bands stay inside it.

| | |
|--|--|
| **In** | Gross `incomeMonthly`, `age`, `residency` |
| **Out** | Employee CPF for the month, and take-home (gross minus that CPF) |
| **Reads it** | People Like You (to turn take-home into `expenseMonthly`), HappiU, Scenario Visualizer |

People Like You, HappiU, and Scenario Visualizer all start from gross salary.
Today GP’s box is `src/cpf.py`, and HappiU and Scenario Visualizer still
deduct CPF in their own engines. Those three calls should be this one box.

### Need parameters

Shared constants for the UNIFIED needs. Need Calculator is the amount
engine and reads this set. HappiU must read the same set when it repeats a
need figure in its payload (hospitalisation, funeral lump), so the two
cannot drift.

| Parameter | Value today | Need |
|-----------|-------------|------|
| Lifestyle share of today’s expenses | Frugal 75%, Stress free 100%, Only the best 125% | `N_RET` |
| Life-support years | between 10 and 25, from `min(max(10, 50 − age), 25)` | `N_INC` |
| Critical illness | 3 years of income replacement + S$200,000 | `N_CRI` |
| Disability | 5 years of income replacement + S$200,000 | `N_TPD` |
| Hospitalisation | 6 months of `incomeMonthly` | `N_HOS` |
| Education course cost | S$75,000 today, grown at `inflationRate` | `N_EDU` |
| General savings / property goal | 1× / 5× annual income, until the customer sets `needAmount` | `N_SAV`, `N_PRP` |

### Risk

Shared. Two inputs, one result. The balance-sheet formula for risk ability
is in [Risk.md](../Risk.md). This page only fixes the attributes every later
component shares.

| Attribute | Session | Who sets it | Meaning |
|-----------|---------|-------------|---------|
| Risk ability | Derived. Code name is capacity | Recalculated from the money attributes, `age`, `ageOfRetirement`, `dependents` | How much market risk the balance sheet can carry. The Score chip calls this risk ability |
| Risk tolerance | `riskTolerance`, default 3 | Customer slider, 1–5 | How much market risk they say they will sit with |
| Suitable band | `riskProfile` | `min(risk ability, risk tolerance)` | The band later components use |

`riskProfile` is what HappiU receives. Until the customer touches the
assumption, the same band seeds `investmentReturn`, which Need Calculator,
Plan Calculator, HappiU, and Scenario Visualizer then read.

People Like You also returns a lifestyle word, `risk_ability`
(conservative / moderate / aggressive). That word is not this risk ability
and is not copied onto the session.

### Stress events

Shared catalog for the Plan stress chips. Scenario Visualizer is the only
reader. HappiU’s `manualEvents` stays off. Defaults live in
`frontend/src/lib/stressEvents.ts` and are copied in `src/sv_payload.py`.
Every row starts **off**. The customer can change the size and the year;
until they do, these are the assumptions.

A year is an offset from today (slider 0 is this year). Scenario Visualizer
columns are 1-based, so offset `n` is engine year `n + 1`. The slider cap
is 80 years.

| Id | Label | Default size | Default year | What Scenario Visualizer applies |
|----|-------|--------------|--------------|----------------------------------|
| `crash` | Market crash | 35% | year 8 | Haircut on invested assets |
| `ccy` | Currency shock | 14% | year 6 | Haircut on liquid assets, at **two-thirds** of the slider (`14% × 2/3`) — the invested book treated as outside SGD |
| `infl` | Inflation shock | +3 pp | years 4–9 | Session `inflationRate` plus this extra, for that span |
| `inc` | Impact on income | −20% | years 5–10 | Salary reduced for that span |
| `death` | Death | S$20,000 | year 17 | One-time cost, and salary goes to 0 |
| `ci` | Critical illness | S$150,000 | year 12 | One-time medical cost |
| `tpd` | Total & permanent disability | S$200,000 | year 15 | One-time medical cost |
| `pa` | Personal accident | S$80,000 | year 10 | One-time medical cost |
| `hosp` | Hospitalisation | S$120,000 | year 9 | One-time hospital bill |
| `care` | Long-term care years | S$90,000 a year | years 30–35 | Extra annual spend for that span |
| `wed` | Wedding / marriage | S$60,000 | year 5 | One-time cost |
| `baby` | Newborn | S$35,000 | year 3 | One-time cost |
| `exp` | Impact on expenses | +15% | years 6–12 | Living spend raised for that span |

### Household seeding

Applied when People Like You fills an empty money picture. Customer edits
(`moneyTouched`) are kept.

| Parameter | Value today | Writes |
|-----------|-------------|--------|
| Spend share of take-home | 67.5% + 5 points per dependant, cap 90% | `expenseMonthly` |
| Saved share of annual surplus | 50% × years since age 21 | liquid assets |
| Liability ratio | 70% of those assets | not stored as the mortgage; mortgage uses the property rule below |
| Cash / investments split | 15% / 85% of liquid assets | `cash`, `investments` |
| Property value by income | S$350k / S$650k / S$850k | `property` |
| Loan to value | 55% of `property` | `mortgage` |
| Assumed life premium rate | 0.31% of sum assured | `policies[].premium` |

### Plan and budget parameters

Plan Calculator and Budget Calculator both read these. Scenario Visualizer
and the plan report copy the premium rate and the free-budget share.

| Parameter | Value today | Used by |
|-----------|-------------|---------|
| Protection premium rate | Dummy 0.078% of sum assured, rounded to S$10. Future: premium-quote API | Plan Calculator, Scenario Visualizer, report |
| Free budget share | 50% of monthly surplus | Plan Calculator (default wealth contribution), Budget Calculator |
| Rounding | lump up to S$1,000; monthly up to S$50 | Plan Calculator |

### HappiU budget envelope

Separate from Budget Calculator. HappiU scores against this envelope; the Plan
screen scores affordability against half of surplus. The two should stay
named apart, and the envelope figures should be configurable with Assumptions.

| Parameter | Value today |
|-----------|-------------|
| `annualBudget` | 1500, fixed |
| Per-need `budget` | `planPrem` when the plan is on, otherwise 200 |
| `gfr` | 5% |
| Benefit rounding when no `planSum` | nearest S$50,000 of `needAmount` |

---

## 4. People Like You

**Reads:** `age` (or `dateOfBirth`), `occupation`, `gender`, `dependents`,
`residency`. Country is Singapore. Does not read Assumptions. Calls the CPF
black box for take-home.

**Writes:** `incomeMonthly`, `expenseMonthly`, `cash`, `investments`,
`property`, `mortgage`, one assumed life `policies` row, `lifeExpectancy`,
`isSmoker`.

**In principle.** An LLM proposes gross monthly income and lifestyle flags
(owns property, smoker, retirement lifestyle). Income is clamped to the
occupation band for Singapore. Everything after that is closed-form:

- Take-home comes from the CPF black box. `expenseMonthly` is a share of
  that take-home, rising with `dependents`.
- Liquid assets are half of annual surplus saved for each year worked since
  21, then split into `cash` and `investments`.
- If the model says they own a home, `property` and `mortgage` come from the
  income band and the loan-to-value parameter. The 70% liability ratio is not
  the mortgage.
- Assumed life cover is the larger of the mortgage (rounded up to the next
  S$100,000) and five years of gross income when there are dependants.
  Premium is the assumed life premium rate times that sum assured.

If this step fails, predict returns 503. Later steps do not run.

---

## 5. Need Profiler

**Reads:** `incomeMonthly`, `expenseMonthly`, liquid assets (`cash` +
`investments`), and the person (age, dependants, property owner). No LLM.
Does not read Assumptions.

**Writes:** `needs[].enabled` and `needs[].priority` for the UNIFIED types.
Four types are on: two protection + `N_RET` + one other growth.

**In principle.** Twelve labels are scored with fixed weights and scaled
0–10. Money factors (income, expense, assets, liabilities) convert **local × FX → USD**, then use USD option-weight bands. Eight labels map onto UNIFIED types. `select_unified_top` always returns two protection + retirement + one other growth (`top_n` is ignored). `priority` is 5 when the score is above 7, otherwise 3. Personal
accident, motor, travel, and farewell are scored and then dropped.

If the profiler is down, GP enables `{N_INC, N_CRI, N_RET, N_PRP or N_SAV}`, or `{N_INC, N_CRI, N_RET, N_EDU}` when `dependents` > 0, with `needAmount` left at 0.

---

## 6. Need Calculator

**Reads:** money attributes (`incomeMonthly`, `expenseMonthly`, `cash`,
`investments`, `mortgage`, `policies`), the enabled needs, goal-card inputs
on each need (lifestyle, `retAge`, `targetYear`, `incomeReplaceMonthly`,
`dependYears`, `bequest`, `monthlyContribution`), Assumptions
(`inflationRate`, `investmentReturn`, `ageOfRetirement`, `lifeExpectancy`),
and the shared Need parameters.

**Writes:** for every UNIFIED need, `needAmount`, `have`, `gap`. Also copies
`ageOfRetirement` from the retirement row.

The UI sends inputs. It does not recompute amounts. `POST /v1/predict` and
`POST /v1/needs` both call `evaluate_session`.

**In principle.** Each enabled need is a lump in today’s (or retirement-day)
money. The years, treatment lumps, lifestyle shares, and income multiples
come from Need parameters. Future spending is discounted at `realReturn`.
Two annuity shapes are used: an ordinary annuity for life and retirement
(first payment a year out), an annuity-due for critical illness and
disability (first payment now).

| Type | `needAmount` is, in principle |
|------|-------------------------------|
| `N_RET` | Today’s annual spend × lifestyle, grown at `realReturn` for T years, then × `a(realReturn, n)` where `n = lifeExpectancy − ageOfRetirement` (LE capped at 99) |
| `N_INC` | Bequest + mortgage (`liabilities`) + an annuity of today’s annual spend over the support years |
| `N_CRI` | Annuity-due of replacement income for the critical-illness years, plus the treatment lump |
| `N_TPD` | Same shape, disability years and lump |
| `N_HOS` | A few months of `incomeMonthly` |
| `N_EDU` | One course cost, grown at `inflationRate` to `targetYear` |
| `N_SAV`, `N_PRP` | The customer’s `needAmount` if already set; otherwise one or five years of income |

`have` is existing cover for protection types (the sum assured, not grown).
For wealth types it is existing savings grown to the goal date at
`realReturn`, plus the future value of `monthlyContribution`. Retirement
`have` is a lump at `ageOfRetirement` and does not include CPF.

```
gap = max(0, needAmount − have)
```

---

## 7. HappiU

**Reads:** the whole session that exists at the call. Before Plan, plan
attributes are empty. With plan, it also reads `planSum`, `planPrem`,
`planMth`, `planLump`, `plansOff`. From Assumptions: `inflationRate`,
`incomeGrowthRate`, `interestRate`, `investmentReturn`, `ageOfRetirement`,
`lifeExpectancy`. It calls the CPF black box, reads Need parameters where a
need figure is repeated, and reads `riskProfile` from Risk.

**Writes:** `preHappiU`, `postHappiU`. GP does not run the Monte Carlo.

**In principle.** GP maps the session into a HappiU body and HappiU scores
financial well-being. Salary sent is gross `incomeMonthly`; HappiU takes
employee CPF from the CPF black box. Cash grows at `interestRate`,
investments at `investmentReturn`. Each enabled need is passed through with
the `needAmount` Need Calculator already stored; any figure HappiU rebuilds
uses Need parameters. `riskProfile` is the suitable band. The budget
envelope in §3 tells HappiU what it may spend on a recommendation; once Plan
Calculator has run, those lines prefer `planSum` and `planPrem`. `preHappiU` is the
score on current holdings. `postHappiU` is the score after HappiU’s
recommendation. Both can move slightly from run to run.

The workbook's **HappiU** tab computes the same score without Monte Carlo:
death, illness and disability become yearly probabilities from HU's tables,
and each year of the expected path is weighted by the chance of being
alive. It lands within a few points of live HU
(see [HappiU.md](HappiU.md#the-workbook-tab-no-monte-carlo)).

---

## 8. Plan Calculator

**Reads:** enabled needs whose `gap` is above 0, money attributes (for
surplus and for caps), and from Assumptions: `inflationRate`,
`investmentReturn`, `ageOfRetirement`. `investmentReturn` follows
`riskProfile` until the customer sets the rate.

**Writes:** `planSum` and `planPrem` on protection needs; `planMth` and
`planLump` on wealth needs; `plansOff` when the customer switches a plan
off; `investMth` and `investLump` as the sums of the wealth plans that are on.

**In principle.** A need is suggested when it is enabled and `gap` > 0.

- Protection (`N_INC`, `N_CRI`, `N_TPD`, `N_HOS`). Default `planSum` equals
  the gap. `planPrem` is the protection premium rate times that sum. The rate
  is a placeholder, not a quoted tariff.
- Wealth (`N_RET`, `N_EDU`, `N_SAV`, `N_PRP`). Horizon is years to
  `ageOfRetirement`, or years to `targetYear`. The lump cap and the monthly
  cap are the amounts that, each on its own, grow to the gap at `realReturn`.
  The default monthly contribution splits half of what is left of annual
  surplus after protection premiums across the suggested wealth needs.
  Default lump is 0.

Growth shown on a wealth plan is the future value of its lump and its
monthly contributions. What is still open is `needAmount − have − that value`.

---

## 9. Budget Calculator

**Reads:** `takeHomeMonthly`, `expenseMonthly`, `investments`, and the Plan
Calculator outputs (`planPrem` of included protection, `planMth` and `planLump` of
included wealth). Uses the free budget share from §3. Does not read the
economic rates.

**Writes:** nothing back onto needs or the plan. It is a comparison the Plan
screen displays.

**In principle.**

```
surplus   = max(0, takeHomeMonthly − expenseMonthly)
free      = half of surplus
monthly   = protection premiums / 12 + wealth contributions
```

`monthly` above `free` is the monthly overspend. Wealth lumps above
`investments` are the lump overspend. This is the affordability check on
the Plan screen. It is separate from the HappiU budget envelope in §3.

---

## 10. Scenario Visualizer

**Reads:** the session after Plan Calculator, including plan attributes, stress events,
and from Assumptions: all six rates, `ageOfRetirement`, and `endAge`. Salary
is gross; employee CPF comes from the CPF black box.

**Writes:** the year-by-year wealth path on the chart. GP does not run the
simulation.

**In principle.** GP maps the same session into a Scenario Visualizer body.
Gross assets are `cash`, `investments`, `property`, and CPF for citizens.
`cash` grows at `interestRate`, `investments` at `investmentReturn`,
`property` at `assetReturn`. Salary is gross annual income and grows at
`incomeGrowthRate`. Employee CPF comes from the CPF black box. The mortgage
is a 20-year annuity at `loanRate`: the level instalment clears the loan,
interest included, and leaves cashflow. The remaining principal is subtracted
from the chart line (`subtractLoanBalances`). The expense-funding panel
uses spendable wealth only; the home and CPF cannot pay living costs
(see [Scenario-visualizer.md](Scenario-visualizer.md)).
The recurring contribution on liquid assets is monthly surplus (take-home
minus `expenseMonthly`). Included plan premiums and contributions go in as
the plan the customer is looking at. Each stress event on the session becomes
an event the engine applies (death, market crash, currency shock,
hospitalisation, long-term care). GP sends `noDeathFlag`, so SV grows each
holding at its own rate and every simulation is the same path. The
workbook's **Scenario Visualizer** tab rebuilds that path year by year and
equals SV (see [Scenario-visualizer.md](Scenario-visualizer.md#the-workbook-tab)).

---

## Formula reference

Algebra for each component. Attribute names match the logic flow above.

| Component | Formulas |
|-----------|----------|
| People Like You | [People-like-you.md](People-like-you.md) |
| Need Profiler | [Need-profiler.md](Need-profiler.md) |
| Need Calculator | [Need-calculator.md](Need-calculator.md) |
| Goal cards | [Goal-cards.md](Goal-cards.md) |
| Plan Calculator | [Plan-calculator.md](Plan-calculator.md) |
| Budget Calculator | [Budget-calculator.md](Budget-calculator.md) |
| HappiU | [HappiU.md](HappiU.md) |
| Scenario Visualizer | [Scenario-visualizer.md](Scenario-visualizer.md) |

---

## Code index

| Concern | Path |
|---------|------|
| Predict orchestration | `src/app.py` `predict` |
| Live need calculator | `src/app.py` `needs` (`POST /v1/needs`) |
| Local engines | `src/pipeline/run.py` |
| PLU / profiler mapping | `src/predict.py` |
| People Like You | `src/pipeline/people_like_you.py` |
| Need Profiler | `src/pipeline/need_profiler.py` |
| Need Calculator | `src/pipeline/need_calculator.py` `evaluate_session` |
| Amount helpers | `src/pipeline/goal_math.py` |
| Goal-card inputs | `frontend/src/lib/needEdit.ts` |
| Risk capacity / return map | `frontend/src/lib/riskCapacity.ts` ([Risk.md](../Risk.md)) |
| Suggested plan + `planAfford` | `GP/frontend/src/lib/planProducts.ts` |
| First product seed | `GP/frontend/src/lib/local.ts` `seedProducts` |
| HU payload / budget lines | `GP/src/hu_payload.py` |
| SV payload | `GP/src/sv_payload.py` |
| HU vs SV field map | [HU-and-SV-payloads.md](../HU-and-SV-payloads.md) |
| Workbook twins of SV / HU | `GP/docs/calculations/deterministic_engines.py` (`twin_sv`, `twin_hu`) |

---

## Open issues

The items below are the ones still open that change a calculation in this
file. Voice and layout items are not listed. Each item has a status, an
issue, the implementation options, an implementation suggestion, and a
conclusion. Status is one of Do now, Do later, Won't do, Needs more info, or Done.
The options are alternatives only. A suggestion is a proposed rule. The
conclusion is the decision.

### FB-36 · Need Calculator, HappiU

**Status.** Done

**Issue.** The same liquid savings (`cash` + `investments`) is counted as
`have` on every wealth need. It should be shared once. The allocation rule
is not signed off.

**Options.**

1. Tag all un-earmarked liquid to `N_RET`; other wealth `have` starts at 0 until the customer funds that need.
2. Split liquid across enabled wealth needs by share of `needAmount`.
3. Split liquid equally across enabled wealth needs.
4. Let the customer allocate `cash` / `investments` to needs.
5. Keep the same pot on every card and show one shared-have note so the gaps are not added.
6. Count liquid only on the highest-priority wealth need that is on.

**Suggestion.** `cash` is never allocated to a need. `investments` (savings)
stay in one central pot and are not allocated to any need until the customer
tags an amount to that need. Tagging is sequential: once an amount is
assigned to a need, only the remainder in the pot can be assigned to the
next need.

**Conclusion.** Same as the suggestion. `cash` is never allocated to a need.
`investments` stay in one central pot until the customer tags an amount, and
only the remainder can go to the next need. Implemented in `need_existing`
and `apply_investment_pot`.

### FB-40 · People Like You, Need Calculator

**Status.** Do later

**Issue.** Your plan keeps the estimated cover. Document upload is not
implemented, and OCR is not implemented, so no sum is read from an uploaded
policy.

**Options.**

1. Keep the estimate until upload is live, then replace it with the parsed sum.
2. Let the customer type the policy sum now; ignore OCR until upload is on.
3. When a document is attached, clear the estimate even if parse is still a mock.
4. Keep the estimate and add any parsed sum (risk of double count).
5. Keep the estimate and mark provenance so the plan does not treat it as a known policy.

**Suggestion.** None selected.

**Conclusion.** Do later, once document upload and OCR are implemented.

### FB-49 · HappiU

**Status.** Needs more info

**Issue.** A goal with a shortfall was reported to score above a fully funded
goal. Checked on one session (age 42, both needs on, 30 simulations) by
changing only `have` on `N_RET` (need 800,000) and `N_INC` (need 500,000).

Fully funded, each need scores 1 and the headline pre-score is 88. With both
short (`N_RET` have 50,000, `N_INC` have 0) the headline is 71: `N_RET` scores
about 0.99 and `N_INC` about 0.43. A short `N_RET` beside a fully funded
`N_INC` scores about 0.99 against 1. A fully funded `N_RET` beside a short
`N_INC` scores 1 against about 0.43.

The inversion is not confirmed. A fully funded need scores at the top. A
shortfall scores the same or lower. A large retirement gap still sits near 1,
so it can look almost as high as a funded goal, and higher than an unfunded
life need. The score is a coverage-efficiency ratio, weighted about 2:1 toward
`N_RET` when only these two needs are on. The frozen HappiU random tables were
missing, so the draws were generated for this run; the levels can move, the
ordering above is the result of this run.

**Options.**

1. Park until a saved `/v1/score` request and response exist for both states.
2. Reproduce with the same session, changing only that goal’s `have` / `gap`.
3. Treat as expected: the score is a weighted coverage-efficiency ratio, not gap size.
4. If it reproduces, keep HappiU as it is and show gap beside the score so the two are not read as the same number.

**Suggestion.** None selected.

**Conclusion.** More tests are required. No immediate changes.

### FB-51 · Need Calculator

**Status.** Done

**Issue.** `dependents` and `N_INC` are linked through spend, not through a
headcount of cover years.

People Like You sets monthly spend as a share of take-home. Zero dependants
is 67.5% of take-home. Each extra dependant adds 5 percentage points, and
the share stops at 90% (`spend_share` in `src/cpf.py`). That share is
`expenseMonthly`.

`N_INC` need amount is a bequest (default 0) plus the mortgage plus an
annuity of today’s annual spend (`expenseMonthly × 12`) over `dependYears`.
`dependYears` comes from age: `min(max(10, 50 − age), 25)`. The number of
dependants is stored on the row and is not an input to that annuity.

So more dependants raise `expenseMonthly`, and a higher `expenseMonthly`
raises the `N_INC` need amount. The years of cover stay the years from age.
Changing dependants does not add a year or a lump per person.

**Options.**

1. Keep support years from age only; dependants change spend, not cover years.
2. Scale `N_INC` years or `needAmount` by the number of dependants.
3. Add extra years or a lump per dependant (for example each child under 21).
4. Leave the formula and document that cover does not follow headcount.
5. Expose `dependYears` on the life card so the customer sets it.

**Suggestion.** None selected.

**Conclusion.** Option 1. No change to the formula: support years stay a
function of age, and dependants change spend, not cover years.

### FB-52 · Scenario Visualizer

**Status.** Done

**Issue.** The chart is labelled Net Wealth. The lead text stays at age 85
instead of the age on the axis.

What the series contains, from the payload GP sends (`src/sv_payload.py`,
`subtractLoanBalances` true, illiquid assets kept):

- Bankable, liquid: cash (`A_SAV`, no new contribution) and investments. Leftover take-home is saved into investments each year.
- Non-bankable, illiquid: the home, at session `property`, and it stays on the line.
- CPF: included for a citizen or permanent resident. Opening OA, SA, MA, and RA are sent as 0; the CPF engine accrues from salary. A foreigner has no CPF on the line.
- Liabilities: remaining mortgage principal is subtracted. The instalment also leaves cashflow for 20 years. No other loan is sent.

After a plan, the same stock also subtracts plan premiums and adds the plan pots. The line is floored at 0.

**Options.**

1. Keep the series; change the label to Gross assets (or Total assets).
2. Subtract remaining mortgage and keep the Net Wealth label.
3. Plot both a gross series and a net series.
4. Fix only the lead text to the age on the axis; leave the series and the label.
5. Subtract the mortgage and make the lead text follow the axis.

**Suggestion.** None selected.

**Conclusion.** Option 1. Keep the series. The chart label is Gross assets.

### FB-54 · Need Calculator

**Status.** Do later

**Issue.** Retired income on the card is today’s `expenseMonthly` times
lifestyle. It did not match a cited document (about S$2,150 at age 30 and
S$3,100 at age 42). Not reproduced. Document upload and OCR are not
implemented, so that document is not read into the session.

**Options.**

1. Park until the cited document and a saved session exist.
2. Keep today’s spend × lifestyle and treat the cited figures as a different rule.
3. If that document uses a wage replacement rate, size retired income from `incomeMonthly` instead.
4. If it uses a cohort spend, seed retired income from People Like You and do not follow the edited expense.
5. Show both today’s spend × lifestyle and the document figure until the rule is signed off.

**Suggestion.** None selected.

**Conclusion.** Do later, once document upload and OCR are implemented.
