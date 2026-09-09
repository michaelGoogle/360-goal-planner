# 360-Goal Planner — calculations and data flow

This document is the **data and formula trail** for FinPlan360. The product
story stays in [Business-overview.md](Business-overview.md). HTTP and modules
stay in [Architecture.md](Architecture.md) and [API.md](API.md).

GP does **not** re-implement People Like You, Need Profiler, or Need Calculator.
Those engines live in **FM**. How they are called, what is LLM vs closed-form,
profiler scoring, and the first `needAmount` fill are in
[People-like-you-and-needs.md](People-like-you-and-needs.md). This file keeps
the short formula trail, then sizes a **suggested plan** and a **budget check**
in the UI. HappiU and the chart consume that session.

Formulas below match the code as of this writing. If they drift, the file named
in each section is the source of truth.

---

## 1. End-to-end flow

```text
About you  (name, age, occupation, residency, dependants, optional docs)
    │
    ▼
POST /v1/predict
    ├── FM People Like You     → income, spend, liquid assets, lifestyle flags
    ├── GP mapping             → cash/investments split, property/mortgage, assumed life
    ├── FM Need Profiler       → which UNIFIED needs are on (top 5)
    ├── GP existing            → cover/savings already allocated to each need
    └── FM Need Calculator     → needAmount and gap (onlyEmpty=true)
    │
    ▼
Your money  (customer may overwrite figures; edits stick)
    │
    ▼
Your score  POST /v1/score → HU
    │   Goal cards: if the customer edits a need, GP recomputes needAmount
    │   in the browser (needEdit.ts) — not a second FM call.
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
| People Like You | FM | `src/predict.py` `_apply_plu` |
| Need Profiler | FM | `src/predict.py` `_needs_from_profiler` |
| Need Calculator | FM `goal_math.py` | `src/predict.py` `_apply_calculator` |
| Goal edit on Score/Plan | **GP UI** | `frontend/src/lib/needEdit.ts` |
| Suggested plan + budget | **GP UI** | `frontend/src/lib/planProducts.ts`, `local.ts` `seedProducts` |
| HappiU budget envelope | GP → HU | `src/hu_payload.py` `_budget_line`, `annualBudget` |
| Projection | SV | `src/sv_payload.py` |

There is **no** FM service named “plan calculator” or “budget calculator”. Plan
sizing and the affordability check are D2C UI logic.

UNIFIED types: `N_INC`, `N_CRI`, `N_TPD`, `N_RET`, `N_EDU`, `N_SAV`, `N_PRP`.

---

## 2. People Like You (FM)

Full write-up: [People-like-you-and-needs.md](People-like-you-and-needs.md) §3.

**Code:** `FM/src/services/people_like_you_service.py`  
**GP call:** `POST /v1/public/people-like-you` (or `/v1/me/onboarding/...` with a Bearer token).  
**GP body:** DOB (from age if missing), occupation, gender, dependants, country/city = Singapore.

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

If FM says they own property, seed a home **on every estimate** (not only the first) from monthly gross income. The loan is **55%** of that property, not FM’s liquid-asset liabilities:

```
property = 350_000 if income < 10_000
         | 650_000 if 10_000 ≤ income ≤ 20_000
         | 850_000 if income > 20_000
mortgage = round(property × 0.55)
```

If FM says they do not own property, clear both `property` and `mortgage`. The UI still keeps values the customer has edited (`moneyTouched`).

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

## 3. Need Profiler (FM)

Full write-up: [People-like-you-and-needs.md](People-like-you-and-needs.md) §4.

**Code:** `FM/src/services/need_profiler_service.py`, weights in `Need_profiler.json`.  
**No LLM.** Weighted scores, scaled 0–10, then the top mapped UNIFIED types are enabled.

GP sends `topN: 5`, policy owner + finance (income, expense, liquid assets).

Twelve AI labels are scored. Only these map into UNIFIED types GP shows:

| Profiler need | UNIFIED |
|---------------|---------|
| Life Protection | `N_INC` |
| Critical Illness | `N_CRI` |
| Disability | `N_TPD` |
| Retirement | `N_RET` |
| Education | `N_EDU` |
| General Savings | `N_SAV` |
| Home Protection | `N_PRP` |

Hospitalisation, personal accident, motor, travel, farewell are scored but never become UNIFIED rows.

**Enable:** walk ranked list, take unique mapped types until `topN` (5). Those `enabled = true`; others off. `weightageScore` is copied from the first matching rank.

GP `priority` = **5** if `weightageScore > 7`, else **3**. If the profiler is down, GP enables `N_INC` and `N_RET` (and `N_EDU` when there are dependants) with `needAmount = 0`.

---

## 4. Need Calculator (FM) — first fill of `needAmount`

Full write-up: [People-like-you-and-needs.md](People-like-you-and-needs.md) §5.

**Code:** `FM/src/services/goal_math.py` (`compute_need_amounts`), same idea as `shared/input_model/src/goalMath.ts`.  
GP sets `existing` first (`need_existing`: policy sum for protection, cash+investments for accumulation), then calls FM with `onlyEmpty: true`.

Let  
`income = monthlyIncome × 12`,  
`expense = monthlyExpense × 12`,  
`r = 0.03`,  
`age` from DOB,  
`ret_age` default 65.

Present-value annuity:

```
PV = PMT × (1 − (1+r)^(−n)) / r     (if r ≈ 0: PMT × n)
```

| Type | FM `needAmount` |
|------|-----------------|
| **N_INC** | `PV(0.5 × expense, r, min(30, max(0, 85 − age)))` |
| **N_CRI** | `5 × income` |
| **N_TPD** | `0.5 × N_INC` |
| **N_RET** | inflate expense to retirement: `expense × (1+r)^(ret_age − age)`, then `PV(that, r, 20)` |
| **N_EDU** | `3 × income` |
| **N_SAV** | `1 × income` |
| **N_PRP** | `5 × income` |

Amounts are rounded to whole currency units. For each **enabled** type:

```
if onlyEmpty and needAmount already > 0: keep it
else: needAmount = computed
gap = max(0, needAmount − existing)
```

Disabled rows are left alone.

GP then copies `existing` onto `existingSumAssured` (protection) or `existingInvestment` (wealth).

---

## 5. Goal cards — how plans are recalculated in the UI

After predict, **Score** and **Plan** can change a need without calling FM again.  
**Code:** `frontend/src/lib/needEdit.ts` (`fillNeedEdit`, `computeNeedAmount`, `needCardHave`, `needCardGap`).

This is a **different** closed form from FM §4. Pencil edits use these. Inflation is the session rate (default **2.3%**), not FM’s 3%.

Lifestyle (retirement income as a share of today’s pay): Frugal **50%**, Stress free **67%**, Only the best **100%** (default Stress free).

### Retirement (`N_RET`) — example

```
retIncomeMonthly = incomeMonthly × lifestyleRate   (rounded to S$50)
years_to_ret     = max(0, retAge − age)
annual_today     = retIncomeMonthly × 12
at_retirement    = annual_today × (1 + inflation)^years_to_ret
needAmount       = round( PV(at_retirement, inflation, 20) )
```

“Have” on the card is **projected savings**, not cash today. The card uses
session `investmentReturn` (default **4.2%**), not the Plan slider `investRet`:

```
realReturn = (1 + investmentReturn) / (1 + inflation) − 1    (floored at 0)
have       = existing × (1 + realReturn)^years_to_ret
gap        = max(0, needAmount − have)
```

Default `existing` for retirement is liquid savings (`cash + investments`) unless the row already has an amount.

### Other needs (after a customer edit)

| Type | `needAmount` |
|------|----------------|
| **N_INC** / **N_TPD** | `incomeReplaceMonthly × 12 × dependYears + liabilities` (default replace = today’s income; depend years 20 if dependants else 10; liabilities default mortgage) |
| **N_CRI** | `incomeReplaceMonthly × 12 × 5` |
| **N_EDU** | `yearCost(region) × courseYears × childrenToFund` (default region Australia, 4 years, children = max(1, dependants)) |
| **N_SAV** / **N_PRP** | customer `amountRequired` (from FM until they change it) |

Education year costs (SGD): Singapore 18k, Australia 12 270, UK 32k, Canada 22k, USA 48k.

Wealth “have” (except retirement) grows `existing` to the target year at `realReturn`; savings/property also add an annuity of `monthlyContribution × 12`. Protection “have” is existing sum assured / policies.

---

## 6. Suggested plan (D2C “plan calculator”)

**Code:** `frontend/src/lib/planProducts.ts`, seeded from `local.ts` `seedProducts`.

A need is **suggested** if it is enabled **and** `needCardGap > 0`. Switching a plan off lists it in `plansOff` (the need can stay on).

### Protection (N_INC, N_CRI, N_TPD)

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
Rate: Plan slider `investRet` (default **7.2%** p.a.), deflated by session inflation.
That is a different field from `investmentReturn` on the goal cards (§5).

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

If no retirement need is enabled, HU still gets a synthetic `N_RET` with `needAmount = expenseMonthly × 12 × 20` and existing = liquid.

Retirement living expense sent to HU: `retIncomeMonthly × 12` if set, else `expenseMonthly × 12`; `expectedLivingExpenseInTheCountry = living × 0.75`; duration 20 years.

---

## 8. Score and projection (no extra need math)

- **Score:** session → `build_happiu_payload` → HU `POST /v1/happi-u`. Monte Carlo and utility are inside HU.  
- **Chart:** session → `build_sv_payload` → SV. Recurring contribution on liquid assets is `max(0, income − expense)` (monthly surplus as an annual-style contribution in the SV body). Stress events and assumption rates pass through as given.

HappiU and the path are **simulation means**; they can move slightly run to run.

---

## 9. Two need-amount models (do not mix them)

| When | Formula set |
|------|-------------|
| First Estimate (`/v1/predict`) | FM `goal_math.py` (§4), `r = 3%` |
| Customer edits a goal card | GP `needEdit.ts` (§5), session inflation (default 2.3%), lifestyle / region / years |

The Score page can therefore show a different retirement lump after a pencil edit than Need Calculator originally wrote. That is intended: the card is an interactive plan, not a replay of FM.

---

## Code index

| Concern | Path |
|---------|------|
| Predict orchestration | `GP/src/app.py` `predict` |
| PLU / profiler / calculator mapping | `GP/src/predict.py` |
| FM People Like You | `FM/src/services/people_like_you_service.py` |
| FM Need Profiler | `FM/src/services/need_profiler_service.py` |
| FM Need Calculator math | `FM/src/services/goal_math.py` |
| Shared TS twin of FM amounts | `shared/input_model/src/goalMath.ts` |
| Goal-card recalc | `GP/frontend/src/lib/needEdit.ts` |
| Suggested plan + `planAfford` | `GP/frontend/src/lib/planProducts.ts` |
| First product seed | `GP/frontend/src/lib/local.ts` `seedProducts` |
| HU payload / budget lines | `GP/src/hu_payload.py` |
| SV payload | `GP/src/sv_payload.py` |
