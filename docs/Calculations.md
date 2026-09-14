# 360-Goal Planner — calculations and data flow

This document is the **data and formula trail** for FinPlan360. The product
story stays in [Business-overview.md](Business-overview.md). HTTP and modules
stay in [Architecture.md](Architecture.md) and [API.md](API.md). Risk capacity,
tolerance, and how they cap net expected returns are in [Risk.md](Risk.md).
The product decisions are in [risk-mgmt.md](risk-mgmt.md).

GP **runs** People Like You, Need Profiler, and Need Calculator in-process
(`src/pipeline/`). How they work is in
[People-like-you-and-needs.md](People-like-you-and-needs.md). This file keeps
the short formula trail, then sizes a **suggested plan** and a **budget check**
in the UI. HappiU and the chart consume that session. What each field becomes in
the HU vs SV bodies is [HU-and-SV-payloads.md](HU-and-SV-payloads.md).

Formulas below match the code as of this writing. If they drift, the file named
in each section is the source of truth.

---

## 1. End-to-end flow

```text
About you  (name, age, occupation, residency, dependants, optional docs)
    │
    ▼
POST /v1/predict
    ├── People Like You        → income, spend, liquid assets, lifestyle flags
    ├── GP mapping             → cash/investments split, property/mortgage, assumed life
    ├── Need Profiler          → which UNIFIED needs are on (top 5)
    ├── GP existing            → cover/savings already allocated to each need
    └── Need Calculator        → needAmount, have, gap
    │
    ▼
Your money  (customer may overwrite figures; edits stick)
    │   POST /v1/needs when income, spend, balances, or cover change
    ▼
Your score  POST /v1/score → HU
    │   Goal cards: slider inputs stay in the session; POST /v1/needs
    │   fills needAmount / have / gap. The browser does not recompute them.
    │   Risk card: capacity from Your money; tolerance slider;
    │   `riskProfile = min(capacity, tolerance)` → HU. See [Risk.md](Risk.md).
    ▼
Your plan   seedProducts + planProducts.ts
    ├── protection plans  (sum assured / premium to close the gap)
    ├── wealth plans      (lump + monthly to grow into the gap)
    ├── budget check      (planAfford: 50% of surplus vs prem + contributions)
    ├── POST /v1/project  → SV chart
    └── POST /v1/score    → HU again (pre vs post HappiU)
```

**Owners**

| Step | Owner | GP files |
|------|--------|----------|
| People Like You | GP `src/pipeline/` | `src/predict.py` `_apply_plu` |
| Need Profiler | GP `src/pipeline/` | `src/predict.py` `_needs_from_profiler` |
| Need Calculator | GP `src/pipeline/need_calculator.py` | `evaluate_session`; `POST /v1/predict` and `POST /v1/needs` |
| Goal-card inputs on Score/Plan | **GP UI** | `frontend/src/lib/needEdit.ts` `patchNeedInputs` (no amount math) |
| Suggested plan + budget | **GP UI** | `frontend/src/lib/planProducts.ts`, `local.ts` `seedProducts` |
| HappiU budget envelope | GP → HU | `src/hu_payload.py` `_budget_line`, `annualBudget` |
| Projection | SV | `src/sv_payload.py` |
| HU vs SV field map | GP | [HU-and-SV-payloads.md](HU-and-SV-payloads.md) |

There is **no** FM service named “plan calculator” or “budget calculator”. Plan
sizing and the affordability check are D2C UI logic.

UNIFIED types: `N_INC`, `N_CRI`, `N_TPD`, `N_HOS`, `N_RET`, `N_EDU`, `N_SAV`, `N_PRP`.

---

## 2. People Like You

Full write-up: [People-like-you-and-needs.md](People-like-you-and-needs.md) §3.

**Code:** `src/pipeline/people_like_you.py`  
**GP call:** in-process `run_people_like_you`.  
**Inputs:** DOB (from age if missing), occupation, gender, dependants, country/city = Singapore.

### What the model does vs what is closed-form

| Output | Source |
|--------|--------|
| Monthly **income**, currency | LLM (Claude if `ANTHROPIC_API_KEY`, else OpenAI), then **clamped** to occupation × country bands in `income_anchors.json` |
| Lifestyle flags (property owner, smoker, retirement lifestyle, …) | LLM — no closed form |
| **Expenses** | Deterministic from income, age, marital, dependants |
| **Assets** (liquid) | Deterministic from surplus × years working |
| **Liabilities** | `assets × 0.7` |

Marital status, if omitted: age `< 30` → single, else married.

### Expenses

People Like You income is **gross** (before employee CPF, including a twelfth of bonus). Spend is a share of **take-home**.

```
employee_cpf = 0                              if Foreigner
             = rate × min(income, 8,000)      otherwise, rounded down
take_home    = income − employee_cpf
share        = min(67.5% + 5% × dependants, 90%)
expenses     = round(take_home × share, 2)
```

Employee rates (not employer): 20% to age 55, then 15% / 9.5% / 5%. The **S$8,000** cap is the CPF ordinary-wage ceiling from 1 Jan 2026, so the most taken off pay at 20% is **S$1,600**. (S$1,200 was 20% of the old S$6,000 ceiling.)

GP reapplies this in `_apply_plu`. Example: S$35,000, citizen, 42, 2 dependants → CPF **S$1,600**, take-home **S$33,400**, spend 77.5% → **S$25,885**. The donut’s “money going out” is spend + CPF; the list row is spend only.

HappiU and SV receive **gross** salary and still deduct CPF themselves.

Income and expenses here are the **monthly** figures GP stores as `incomeMonthly` / `expenseMonthly`. CPF is derived, not stored.

### Assets and liabilities

If income, expenses, and age `> 21`:

```
savings_per_month = take_home − expenses
assets = max(0, savings_per_month × 12 × 0.5 × (age − 21))
liabilities = assets × 0.7
```

Otherwise `assets = 0`. Property **value** is not computed by FM — only a boolean “owns property”.

### What GP stores (`_apply_plu`)

Prefer `onboarding.data.finance`, else `result`:

| FM | GP session |
|----|------------|
| `monthlyIncome` / `result.income` | `incomeMonthly` |
| `monthlyExpense` / `result.expenses` | `expenseMonthly` |
| `liquidAssetValue` / `result.assets` | split `cash = round(assets × 0.45)`, `investments = round(assets × 0.55)` |

If People Like You says they own property, seed a home **on every estimate** (not only the first) from monthly gross income. The loan is **55%** of that property, not the liquid-asset liabilities formula:

```
property = 350_000 if income < 10_000
         | 650_000 if 10_000 ≤ income ≤ 20_000
         | 850_000 if income > 20_000
mortgage = round(property × 0.55)
```

If People Like You says they do not own property, clear both `property` and `mortgage`. The UI still keeps values the customer has edited (`moneyTouched`).

**Assumed life cover** (GP, not FM), if the result is `> 0`:

```
mortgage_cover = nearest S$100,000 of mortgage   (only if property > 0; halves round up)
dependants_cover = round(incomeMonthly × 12 × 5)  (only if dependants > 0)
sum_assured = max(mortgage_cover, dependants_cover)
premium = round(sum_assured × 0.0031)
```

Existing non-life policies are kept. `source` becomes `people-like-you`.

If People Like You is down or `success: false`, predict returns **503**. There is no occupation-band fallback on this path.

---

## 3. Need Profiler

Full write-up: [People-like-you-and-needs.md](People-like-you-and-needs.md) §4.

**Code:** `src/pipeline/need_profiler.py`, weights in `src/pipeline/prompts/Need_profiler.json`.  
**No LLM.** Weighted scores, scaled 0–10, then the top mapped UNIFIED types are enabled.

GP sends `topN: 5`, policy owner + finance (income, expense, liquid assets).

Twelve AI labels are scored. Only these map into UNIFIED types GP shows:

| Profiler need | UNIFIED |
|---------------|---------|
| Life Protection | `N_INC` |
| Critical Illness | `N_CRI` |
| Disability | `N_TPD` |
| Hospitalisation | `N_HOS` |
| Retirement | `N_RET` |
| Education | `N_EDU` |
| General Savings | `N_SAV` |
| Home Protection | `N_PRP` |

Personal accident, motor, travel and farewell are scored but never become UNIFIED rows.

**Enable:** walk ranked list, take unique mapped types until `topN` (5). Those `enabled = true`; others off. `weightageScore` is copied from the first matching rank.

GP `priority` = **5** if `weightageScore > 7`, else **3**. If the profiler is down, GP enables `N_INC` and `N_RET` (and `N_EDU` when there are dependants) with `needAmount = 0`.

---

## 4. Need Calculator — `needAmount`, `have`, `gap`

Full write-up: [People-like-you-and-needs.md](People-like-you-and-needs.md) §5.

**Code:** `src/pipeline/need_calculator.py` (`evaluate_session`).  
**HTTP:** `POST /v1/predict` (first fill) and `POST /v1/needs` (every later input change).

There is **one** engine. The UI sends slider and money inputs; it does not
recompute amounts.

GP sets `existing` from policies (protection) or cash+investments (wealth)
when the row has no amount yet (`need_existing`). CPF is **not** in the
retirement pot (private retirement only). Session inflation (default
**2.3%**) and `investmentReturn` (workbook fallback **4.2%**) feed the
calculator — not a fixed 3%. Lifestyle spend on Your Money cannot be 0.

Lifestyle (share of **today’s expenses**): Frugal **75%**, Stress free
**100%**, Only the best **125%** (default Stress free). Retirement age
defaults to **65**. Years in retirement: **85 − retAge**.

Every non-retirement formula below follows the **TFM_2604 Needs Calculator
workbook** (`Input Output` rows 62–95). GP keeps the Excel formula *shapes* but
uses **session rates** rather than the workbook's per-country rate table, and its
constants are **Singapore-only, in SGD** — there is no country-of-study or
country-of-treatment lookup.

Two annuity conventions, because the workbook is not consistent: life and
retirement use an ordinary annuity, critical illness and disability an
annuity-due.

```
a(r, n)    = (1 − (1+r)^(−n)) / r            ordinary — first payment discounted
aDue(r, n) = (1 − vⁿ) / (1 − v), v = 1/(1+r)  annuity-due — first undiscounted
supportYears(age) = min(max(10, 50 − age), 25)          Excel E12
realReturn = (1 + investmentReturn) / (1 + inflation) − 1    (floored at 0)
T = retAge − age
n = 85 − retAge
annualSpend = expenseMonthly × 12 × lifestyleRate
```

| Type | `needAmount` |
|------|----------------|
| **N_RET** | `annualSpend × (1+realReturn)^T × a(realReturn, n)` — lump **at retirement** |
| **N_INC** (Excel `C64`) | `bequest + liabilities + expenseMonthly × 12 × a(realReturn, dependYears)` — driven by **spend**, not income. `dependYears` defaults to `supportYears(age)`, `liabilities` to the mortgage, `bequest` to 0 |
| **N_CRI** (Excel `C73`) | `incomeReplaceMonthly × 12 × aDue(realReturn, 3) + 200,000` |
| **N_TPD** (Excel `C82`) | `incomeReplaceMonthly × 12 × aDue(realReturn, 5) + 200,000` |
| **N_HOS** (Excel `C91`) | `incomeMonthly × 6` |
| **N_EDU** (Excel `F73`) | `75,000 × (1 + inflation)^(targetYear − thisYear)` — one total course cost, no course-years or children multiplier |
| **N_SAV** / **N_PRP** | customer `needAmount` if already `> 0`; else **1×** / **5×** annual income (GP-only; the workbook has neither) |

Singapore constants (`src/pipeline/goal_math.py`): critical illness **3 years + S$200,000** treatment, disability **5 years + S$200,000**, hospitalisation **6 months** of income, education **S$75,000** total. They are Singapore-realistic SGD equivalents of the workbook's USD figures and are **pending business sign-off**. Education discounts at **inflation**, not the real return, matching the workbook. The workbook's `Ward A/B Cost`, `Private Factor` and Farewell (funeral cost) columns are deliberately not implemented.

Amounts are rounded to whole currency units. Sample profile (age 42, S$6,800/mo income, S$4,000/mo spend, S$200,000 mortgage, education target year +10): N_INC **634,401**, N_CRI **440,363**, N_TPD **593,390**, N_HOS **40,800**, N_EDU **94,149**.

### Projected have and gap

“Have” on the card is **projected savings** (wealth) or existing cover
(protection), not merely cash today. Retirement need and have are both
lumps at the retirement date so plan FV math stays in the same unit.

```
N_RET have     = FV(privateRetirement, realReturn, T)
                 + FV of (monthlyContribution × 12) for T years
                 (contribution default 0; years locked to T; no CPF)
other wealth   = existing grown to targetYear at realReturn
                 (+ contribution annuity for N_SAV / N_PRP)
protection     = existing sum assured
gap            = max(0, needAmount − have)
```

Default private retirement is liquid savings (`cash + investments`) unless
the row already has an amount. Later retirement shortens `n` and grows
have for more years, so the gap falls.

---

## 5. Goal cards — inputs only

After predict, **Score** and **Plan** change a need by writing slider
fields onto the session and calling **`POST /v1/needs`** (debounced).  
**Code:** `frontend/src/lib/needEdit.ts` (`patchNeedInputs`, `fillNeedEdit`).

`fillNeedEdit` reads stored fields for the editor. `needCardHave` /
`needCardGap` read `n.have` and `n.gap` from the last calculator
response.

---

## 6. Suggested plan (D2C “plan calculator”)

**Code:** `frontend/src/lib/planProducts.ts`, seeded from `local.ts` `seedProducts`.

A need is **suggested** if it is enabled **and** `needCardGap > 0`. Switching a plan off lists it in `plansOff` (the need can stay on).

### Protection (N_INC, N_CRI, N_TPD, N_HOS)

Default sum assured = the current card gap (rounded).  
Indicative annual premium:

```
indicative = round((sum × 0.00078) / 10) × 10
slider max premium = max(indicative × 2, 200)
default premium    = round((max / 2) / 10) × 10
```

That **0.00078** factor is a D2C placeholder, not a quoted tariff.

### Wealth (N_RET, N_EDU, N_SAV, N_PRP)

Horizon: years to retirement age, or `targetYear − this year`.  
Rate: session `investmentReturn` on the Plan **net expected returns** slider
(seeded from the suitable risk band; workbook fallback **4.2%** p.a. after
product costs), deflated by session inflation. (`investRet` is the same rate
in percent.) Mapping: [Risk.md](Risk.md) §6.

Lump and monthly caps are the amounts that, **alone**, grow to the remaining gap:

```
lump_cap     = PV of gap over horizon at real plan rate   (round up to S$1,000)
monthly_cap  = annual PMT to hit gap, / 12                 (round up to S$50)
```

Default monthly (first seed), split across suggested wealth needs:

```
annual_surplus = max(0, (income − expense) × 12)
left           = max(0, annual_surplus − life_premium)
share          = round(left × 0.6 / 12 / n_wealth / 50) × 50
planMth[type]  = min(share, monthly_cap)
planLump[type] = 0
```

`investMth` / `investLump` on the session are the **sums** of included wealth plans. Chart / HU see those totals, not the per-goal split.

Growth shown on a wealth plan:

```
FV = lump × (1+r)^n  +  FV_annuity(monthly × 12, r, n)
remain = needAmount − have − FV
```

---

## 7. Budget check (D2C) and HappiU budget envelope

### What the Plan screen treats as budget

**Code:** `planAfford` in `planProducts.ts`.

```
available = max(0, incomeMonthly − expenseMonthly)     // monthly surplus
free      = round(available × 0.5)                    // FREE_BUDGET_SHARE
premMth   = (sum of included protection annual premiums) / 12
contribMth = sum of included wealth monthly contributions
monthly   = premMth + contribMth
monthlyOver = monthly − free
lumpOver    = wealth lumps − liquid savings
```

So the “budget” the customer sees is **half of monthly surplus**, compared with plan premiums plus savings contributions. It is not FM’s Need Calculator.

### What HU receives as budget

**Code:** `src/hu_payload.py`.

- `commonDetails.annualBudget` = **1500** (fixed placeholder).  
- Per enabled need, `solutionOptimizerOutput.segregatedBudget[]`:

```
benefitAmount = needAmount rounded to nearest S$50,000
budget        = annualPremium on the need, or 200
growthRate    = 0.035 if accumulation else 0
gfr           = 0.05
```

If no retirement need is enabled, HU still gets a synthetic `N_RET` with
`needAmount = expenseMonthly × 12 × (85 − retAge)` and existing = liquid.

Retirement living expense sent to HU: `expenseMonthly × lifestyleRate × 12`;
`expectedLivingExpenseInTheCountry = living × 0.75`;
`durationOfRetirement = 85 − retAge` (same value on SV).

---

## 8. Score and projection (no extra need math)

Field-by-field map: [HU-and-SV-payloads.md](HU-and-SV-payloads.md). Keep that
page in the same commit as `hu_payload.py` / `sv_payload.py`.

- **Score:** session → `build_happiu_payload` → HU `POST /v1/happi-u`. Monte Carlo and utility are inside HU.  
- **Chart:** session → `build_sv_payload` → SV. Gross assets: cash, investments, property, and CPF for citizens. Mortgage instalments hit cashflow; remaining principal is not subtracted. Recurring contribution on liquid assets is `max(0, take-home − expense)` (monthly surplus as an annual-style contribution in the SV body). Every Goal Planner stress row maps to an SV `manualEvents` type the engine applies (GP offset `0` → SV year `1`, slider value in `config` or `impact`). Death zeros salary; crash haircuts invested assets; currency shock haircuts liquid assets; hospitalisation is a hospital bill; long-term care is an expense span. Assumption rates pass through as given.

HappiU and the path are **simulation means**; they can move slightly run to run.

---

## 9. One need-amount model

`POST /v1/predict` and `POST /v1/needs` call the same `evaluate_session`.
Pencil edits do not switch formula set. Suggested plan sizing
(`planProducts.ts`) still runs in the UI and is not this calculator.

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
| Risk capacity / return map | `frontend/src/lib/riskCapacity.ts` ([Risk.md](Risk.md)) |
| Suggested plan + `planAfford` | `GP/frontend/src/lib/planProducts.ts` |
| First product seed | `GP/frontend/src/lib/local.ts` `seedProducts` |
| HU payload / budget lines | `GP/src/hu_payload.py` |
| SV payload | `GP/src/sv_payload.py` |
| HU vs SV field map | [HU-and-SV-payloads.md](HU-and-SV-payloads.md) |
