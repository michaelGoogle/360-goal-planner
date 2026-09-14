# People Like You, Need Profiler, and Need Calculator

How FinPlan360 turns **About you** into a money estimate and a set of goal
amounts. The engines run **in-process in GP** (`src/pipeline/`), ported from
FM. `POST /v1/predict` calls them in order, maps the JSON into the session,
and returns that to the UI. FM still exposes the same public/onboarding
routes for the portal; GP no longer calls them for Estimate.

The product story is in [Business-overview.md](Business-overview.md). The rest
of the formula trail (goal-card edits, suggested plan, HappiU budget) stays in
[Calculations.md](Calculations.md). Risk capacity vs People Like You
`risk_ability` is in [Risk.md](Risk.md). HTTP wiring is in
[Architecture.md](Architecture.md).

If a formula here drifts, the file named in each section is the source of truth.

---

## 1. What each step is for

| Step | Question it answers | LLM? |
|------|---------------------|------|
| **People Like You** | What does someone like this typically earn, spend, own, and prefer? | Yes (income + lifestyle). Spend, cash, and loans are closed-form. |
| **Need Profiler** | Which of twelve life needs matter most, so which UNIFIED goals should be on? | No. Weighted scores from a spreadsheet (`Need_profiler.json`). |
| **Need Calculator** | For each UNIFIED goal, what lump (`needAmount`), projected have, and gap vs existing? | No. Excel-aligned formulas with session real returns in `evaluate_session`. |

GP then:

- Recomputes CPF, spend, liquid assets, property, and assumed life cover
  (`src/predict.py`, `src/cpf.py`).
- Sets `existing` on each need (policies vs cash+investments).
- Shows the customer **Your money**, where pencil edits stick (`moneyTouched`).

UNIFIED types GP shows as goals: `N_INC`, `N_CRI`, `N_TPD`, `N_HOS`, `N_RET`, `N_EDU`,
`N_SAV`, `N_PRP`.

---

## 2. Call chain (`POST /v1/predict`)

```text
About you  (name, age, occupation, residency, dependants, gender)
    │
    ▼
GP  POST /v1/predict
    │
    ├─ 1. run_people_like_you     (Claude / OpenAI + closed-form spend)
    │      maps finance → session  (_apply_plu)
    │      If this raises → HTTP 503. No occupation-band fallback.
    │
    ├─ 2. run_need_profiler       topN = 5, including the PLU lifestyle blob
    │      maps ranked needs → session.needs  (_needs_from_profiler)
    │      If this raises → enable N_INC + N_RET (and N_EDU if dependants), amounts 0.
    │
    ├─ 3. need_existing(need, session)        policies for protection; cash+investments for wealth
    │
    └─ 4. evaluate_session        needAmount, have, gap
           (`src/pipeline/need_calculator.py`)
           If this raises → amounts stay 0; note in the response.

Later slider / money / rate edits: POST /v1/needs → same evaluate_session.
```

**Code:** `GP/src/app.py` `predict`, `GP/src/pipeline/run.py`, `GP/src/predict.py`.

GP always uses `country` / `city` = Singapore on this path.

---

## 3. People Like You

**Code:** `GP/src/pipeline/people_like_you.py`  
**Prompt:** `GP/src/pipeline/prompts/people_like_you_all_fields.json`  
**Income bands:** `GP/src/pipeline/prompts/income_anchors.json`  
**Inputs:** DOB (synthesised from age if missing), occupation, gender,
dependants, residency, Singapore location.

### 3.1 What the model predicts vs what is calculated

The LLM (Claude if `ANTHROPIC_API_KEY`, else OpenAI) returns **only** lifestyle
and a monthly **gross** income. Temperature is 0.1. It must answer with a JSON
object, no markdown.

| Field | Source |
|-------|--------|
| `income` (monthly gross, local currency) | LLM, then **clamped** to occupation × country bands when the title matches `income_anchors.json` |
| `currency` | LLM (ISO code; GP is SGD) |
| `risk_ability` | LLM: conservative / moderate / aggressive. GP Estimate **does not** use this as the Score risk chip; capacity is calculated from Your money ([Risk.md](Risk.md)). |
| `price_sensitivity` | LLM: low / medium / high |
| `property`, `car`, `travelling`, `is_smoker` | LLM booleans |
| `ward_type`, `hospitalization_type` | LLM (Single/Double/Ward, Public/Private) |
| `retirement_lifestyle` | LLM: Basic / Comfortable / Luxurious |
| `sports` | LLM free text |
| `life_expectancy` | LLM integer |
| **`expenses`** | Closed form from income, age, residency, dependants — **not** the model |
| **`assets`** (liquid) | Closed form from monthly surplus × years since age 21 |
| **`liabilities`** | `assets × 0.7` (FM’s liquid-side loans — GP does **not** use this as the mortgage) |

Marital status, if omitted: age `< 30` → single, else married. It is passed into
the prompt; the spend formula no longer uses it.

If the occupation is **unmatched** (baker, auditor, mechanical engineer, …),
there is no clamp: the LLM number is kept.

### 3.2 Income (gross)

People Like You income is **monthly gross**: before the employee’s own CPF,
including a twelfth of bonus. It is not take-home and not a payslip.

1. The prompt includes Singapore monthly bands (and local-currency bands when
   the country is not Singapore) so the model stays inside a typical
   jobholder’s range, not listed-company packages.
2. After JSON parse, if `get_income_bounds(occupation, country, city)` finds a
   band, income is clamped: `min(max(income, min), max)`.
3. Invalid or missing income becomes `0`.

GP stores this as `incomeMonthly`.

### 3.3 Employee CPF and spend

Same rules in `src/cpf.py`. Predict **recomputes** spend and liquid assets in
`_apply_plu` so the session always uses GP’s formula.

```
employee_cpf = 0                              if residency is Foreigner
             = floor(rate × min(gross, 8,000)) otherwise
take_home    = gross − employee_cpf
share        = min(67.5% + 5% × dependants, 90%)
expenses     = round(take_home × share, 2)
```

Employee rates (not employer): **20%** to age 55, then **15% / 9.5% / 5%**.
The **S$8,000** cap is the CPF ordinary-wage ceiling from 1 Jan 2026, so the
most taken off pay at 20% is **S$1,600**. Tax is not deducted.

Example: S$9,500 gross, Singapore Citizen, age 42, 2 dependants → CPF
**S$1,600**, take-home **S$7,900**, spend 77.5% → **S$6,122.50**.

The Your money donut’s “money going out” is spend **plus** CPF; the list row
is spend only. HappiU and SV still receive **gross** salary and deduct CPF
themselves.

### 3.4 Liquid assets (FM) and how GP splits them

If income, expenses, and age `> 21`:

```
savings_per_month = take_home − expenses
assets            = max(0, savings_per_month × 12 × 0.5 × (age − 21))
liabilities       = assets × 0.7
```

Otherwise liquid `assets = 0`. That 0.5 is “half of surplus is saved”. Years
working start at 21, not years in the current job.

GP then splits liquid assets:

```
cash         = round(assets × 0.45)
investments  = round(assets × 0.55)
```

### 3.5 Property and mortgage (GP, not FM)

FM only returns a boolean `ownershipInformation.property`. Property **value**
is seeded on every estimate when that flag is true:

```
property = 350,000 if incomeMonthly < 10,000
         | 650,000 if 10,000 ≤ incomeMonthly ≤ 20,000
         | 850,000 if incomeMonthly > 20,000
mortgage = round(property × 0.55)
```

If they do not own property, both are cleared. Customer pencil edits on Your
money still win (`moneyTouched`).

### 3.6 Assumed life cover (GP, not FM)

If the result is greater than zero, GP inserts a Life Protection policy:

```
mortgage_cover    = nearest S$100,000 of mortgage   (only if property > 0; halves round up)
dependants_cover  = round(incomeMonthly × 12 × 5)    (only if dependants > 0)
sum_assured       = max(mortgage_cover, dependants_cover)
premium           = round(sum_assured × 0.0031)
```

Existing non-life policies are kept. `source` becomes `people-like-you`.

This assumed life sum becomes **existing** cover on `N_INC` for the Need
Calculator (see §5.2).

### 3.7 Failure

If People Like You is down, returns non-JSON, or `success: false`, predict
returns **503**. There is no silent occupation-band fallback on this path.

---

## 4. Need Profiler

**Code:** `GP/src/pipeline/need_profiler.py`,
`GP/src/pipeline/onboarding.py` `build_profiler_profile`  
**Weights:** `GP/src/pipeline/prompts/Need_profiler.json`  
**No LLM.**

Profiler answers: *which needs rank highest?* It does **not** compute dollar
amounts. That is the calculator.

### 4.1 What predict passes in

```text
topN: 5
policyOwner: dateOfBirth, gender, occupation, dependents, country, city,
             isSmoker (session or PLU), ageOfRetirement
finance:     monthlyIncome, monthlyExpense, liquidAssetValue (cash + investments)
peopleLikeYou: the PLU response (ownership, travel, sports, hospital/ward, liabilities)
```

`build_profiler_profile` flattens that into Age, Gender, Dependents,
Occupation, Smoker, MonthlyIncome, HomeOwnership, and so on. Missing keys are
skipped (they add 0). Because the PLU blob is in-process, home/car ownership
now affect ranking (Home Protection ranks higher when People Like You said
they own a flat).

### 4.2 Twelve AI labels, eight UNIFIED cards

Every run scores **twelve** labels. Only eight map onto goal cards:

| Profiler label | `needKey` | UNIFIED | Shown on Score / Plan? |
|----------------|-----------|---------|------------------------|
| Life Protection | `lifeProtection` | `N_INC` | Yes |
| Critical Illness | `criticalIllness` | `N_CRI` | Yes |
| Disability | `disability` | `N_TPD` | Yes |
| Retirement | `retirement` | `N_RET` | Yes (card title **Private Retirement**) |
| Education | `education` | `N_EDU` | Yes **if enabled** |
| General Savings | `generalSavings` | `N_SAV` | Yes |
| Home Protection | `home` | `N_PRP` | Yes |
| Hospitalization | `hospitalization` | `N_HOS` | Yes |
| Farewell | `farewell` | — | Scored only |
| Personal Accident | `personalAccident` | — | Scored only |
| Car Protection | `motor` | — | Scored only |
| Travel Protection | `travel` | — | Scored only |

`Need_profiler.json` has **no** per-need weights for the label `Education`,
so Education almost always scores **0** and is rarely turned on by ranking.
(If the profiler HTTP call itself fails, GP still enables `N_EDU` when there
are dependants — see §4.6.)

### 4.3 How a raw score is built

For each of the twelve labels:

```
raw_score(need) = Σ  factor_weight(factor, need) × option_weight(factor, profile_value)
```

- **`needs_factor_weights`** — how much this *factor* matters for this *need*
  (e.g. Dependants × Life Protection = 4).
- **`weight_options`** — which *bucket* the person falls in (e.g. 2+ dependants
  = 4.0; no dependants = 0.0).

If the profile value is missing, or that need is not listed under the factor,
the term is skipped.

**Age buckets:** below 21 → 1; 21–30 → 2; 31–40 → 3; above 40 → 4.  
**Dependants:** 0 / 1 / 2+.  
**Occupation:** self-employed / entrepreneur / freelance → 2; else salaried → 1.  
**Smoker:** smoker 3, non-smoker 1 (when those options exist).  
**Existing cover:** boolean “already has this insurance?” — GP sends 0, so
“False” weights apply.  
**Income / expense / assets / liabilities:** the value is multiplied by
**0.75** (a USD-ish scale from the original spreadsheet) then bucketed. A
typical Singapore income therefore lands in the **lowest** income-need weight
(0.0 above ~S$3,600/month). Dependants, occupation, and age still move the
ranking.

Lifestyle and sports only match if the string equals the spreadsheet options
(`frugal` / `stress-free` / `only the best`; sports buckets). People Like You
uses different words (`Comfortable`, `Running`), so those factors often add 0
even when a PLU blob is present.

### 4.4 Scale 0–10, rank, pick top 5 UNIFIED

1. Sort all twelve by raw score, high to low.
2. Optional `preferredNeeds` (GP does not send this): boost matching keys.
3. **Min–max scale** onto 0–10:

   ```
   scaled = (raw − min_raw) / (max_raw − min_raw) × 10
   ```

   If every raw score is equal, scaled = 5.0.
4. Annotate ranking 1…12 and a coarse priority: scaled ≤5 low, ≤7 medium,
   else high.
5. Walk the ranked list. Collect **unique UNIFIED types** until `topN` (5).
   Unmapped labels (hospital, travel, …) are skipped for this set.
6. Those types get `enabled = true`; other UNIFIED rows are **off**.
   `weightageScore` is the scaled score of the first matching rank.

GP `priority` on a need row is **5** if `weightageScore > 7`, else **3**.

Need amounts are still 0 at this point.

### 4.5 What this means in practice

Profiler is a **priority sort**, not a quote. A 42-year-old with dependants
usually ranks Life Protection high (dependants weight 4 on that need).
Retirement, savings, critical illness, and disability compete for the other
slots. Home Protection only ranks strongly when `HomeOwnership` is true — which
the GP body does not currently set, even if People Like You said they own a
flat.

Enabled flags are what the Score page shows as on. The customer can still
toggle goals later; that does not re-call the profiler.

### 4.6 If the profiler is down

GP does not fail the whole predict. It enables `N_INC` and `N_RET`, plus
`N_EDU` when `dependents > 0`, all with `needAmount = 0`, and adds a note.

---

## 5. Need Calculator

**Code:** `GP/src/pipeline/need_calculator.py` (`evaluate_session`)  
**HTTP:** `POST /v1/predict` and `POST /v1/needs`

The calculator does **not** rank needs. It fills **dollars** (`needAmount`,
projected `have`, `gap`) for every UNIFIED type from the current session.

### 5.1 Inputs

The session body (same as predict): money, rates, `ageOfRetirement`, and
`needs[]` slider fields (`retAge`, `lifestyle`, `existing`, `bequest`, …).

`dateOfBirth` or `age` is required for horizons. Retirement age defaults to
**65**. Inflation is the session rate (default **2.3%**), not a fixed 3%.
Investment return defaults to **4.2%**.

### 5.2 Existing cover / savings

For each need, `existing` is the slider amount if already set; otherwise
`need_existing` in `hu_payload.py`:

| Kind | Types | `existing` |
|------|-------|------------|
| Protection | `N_INC`, `N_CRI`, `N_TPD`, `N_HOS` | Sum of matching policy `sum` (Life / CI / TPD / Hospitalisation) |
| Wealth | `N_RET`, `N_EDU`, `N_SAV`, `N_PRP` | `cash + investments` (private; not CPF) |

The assumed life policy from People Like You therefore reduces the **life**
gap. It does not reduce critical-illness or TPD.

### 5.3 Amount formulas

Lifestyle (share of **today’s expenses**): Frugal **75%**, Stress free
**100%**, Only the best **125%** (default Stress free).
`retIncomeMonthly` stored on the row is `round_to(expenseMonthly × rate, 50)`
(not shown on the card). Retirement age defaults to **65**. Years in
retirement `n = 85 − retAge`. Your Money blocks expense at 0.

Two annuity conventions, mirroring the workbook: retirement and life use an **ordinary** annuity `a(r, n)`, critical illness and disability an **annuity-due** `aDue(r, n) = (1 − vⁿ)/(1 − v)` with `v = 1/(1+r)`.

```
PV(PMT, r, n) = PMT × (1 − (1+r)^(−n)) / r     if r ≉ 0
              = PMT × n                          if r ≈ 0
n ≤ 0 or PMT ≤ 0 → 0
```

```
realReturn = (1 + investmentReturn) / (1 + inflation) − 1    (floored at 0)
T = retAge − age
annualSpend = expenseMonthly × 12 × lifestyleRate
```

Amounts are rounded to whole currency units (`round_money`).

| Type | `needAmount` | Meaning |
|------|----------------|---------|
| **N_RET** | `annualSpend × (1+realReturn)^T × a(realReturn, n)` | Lump **at retirement** (Excel Needs Calculator shape; no PPP) |
| **N_INC** | `bequest + liabilities + expenseMonthly × 12 × a(realReturn, dependYears)` | Excel `C64`: settle debts, leave any legacy, and fund household **spend** for the support years |
| **N_CRI** | `incomeReplaceMonthly × 12 × aDue(realReturn, 3) + 200,000` | Excel `C73`: three years of income plus Singapore treatment cost |
| **N_TPD** | `incomeReplaceMonthly × 12 × aDue(realReturn, 5) + 200,000` | Excel `C82`: five years of income plus Singapore treatment cost |
| **N_HOS** | `incomeMonthly × 6` | Excel `C91`: six months to recover |
| **N_EDU** | `75,000 × (1 + inflation)^(targetYear − thisYear)` | Excel `F73`: one Singapore course total, inflated to the start year (no course-years or children multiplier) |
| **N_SAV** | customer `needAmount` if `> 0`, else `1 ×` annual income | Savings target |
| **N_PRP** | customer `needAmount` if `> 0`, else `5 ×` annual income | Property target |

Non-retirement formulas follow the **TFM_2604 Needs Calculator** workbook (`Input Output` rows 62–95) with GP session rates. Constants are **Singapore-only, SGD**: critical illness 3 years + **S$200,000**, disability 5 years + **S$200,000**, hospitalisation **6 months**, education **S$75,000** total; `supportYears(age) = min(max(10, 50 − age), 25)` (Excel `E12`). The costs are Singapore-realistic equivalents of the workbook's USD figures and are **pending business sign-off**. Farewell (funeral cost) and the workbook's ward / private-factor columns are not implemented.

Worked sketch (age 42, expense S$4,000/month, Stress free, retire 65, inflation 2.3%, investment return 3.5%):

- Annual spend in retirement = S$48,000 (100% of expenses).
- `T = 23`, `n = 20`, `realReturn ≈ 1.17%`.
- **N_RET** `needAmount` grows that spend at real return to retirement, then takes the 20-year annuity. Retiring later shortens `n` and usually **lowers** the lump.
- With income S$6,800/month and a S$200,000 mortgage, the Excel-aligned amounts are **N_INC 634,401**, **N_CRI 440,363**, **N_TPD 593,390**, **N_HOS 40,800**, and **N_EDU 94,149** ten years out.

### 5.4 Have and gap

```
N_RET have   = FV(privateRetirement, realReturn, T)
               + FV of (monthlyContribution × 12) for T years
               (default contribution 0; CPF excluded)
other wealth = existing grown to targetYear at realReturn
               (+ contribution annuity for N_SAV / N_PRP)
protection   = existing
gap          = max(0, needAmount − have)
```

Disabled rows are still computed so toggling them on does not need a second
formula. GP copies `existing` onto `existingSumAssured` (protection) or
`existingInvestment` (wealth).

Later retirement **lowers** the retirement gap: years in retirement shrink
and the private pot (plus any contribution) has more years to grow.

### 5.5 If the calculator is down

Predict still succeeds. Amounts stay 0 until `/v1/needs` or later engines run.
A note is returned (`Need Calculator unavailable…`). `/v1/needs` itself
returns **503**.

---

## 6. After predict

The customer can still toggle which goals are on; that does not re-call the
profiler. Amounts refresh through **`POST /v1/needs`** (debounced) when
goal sliders, money figures, or assumption rates change.

Suggested plan products and the half-surplus budget check are D2C UI
(`planProducts.ts`). There is no FM “plan calculator”.

---

## 7. Code index

| Concern | Path |
|---------|------|
| Predict orchestration | `src/app.py` `predict` |
| Live need calculator | `src/app.py` `needs` (`POST /v1/needs`) |
| Local engines | `src/pipeline/run.py` |
| Session mapping | `src/predict.py` |
| CPF / spend (recompute) | `src/cpf.py` |
| Existing cover | `src/hu_payload.py` `need_existing` |
| People Like You | `src/pipeline/people_like_you.py` |
| PLU prompt + income bands | `src/pipeline/prompts/` |
| Need Profiler | `src/pipeline/need_profiler.py` |
| Profiler weights | `src/pipeline/prompts/Need_profiler.json` |
| Profile flatten | `src/pipeline/onboarding.py` `build_profiler_profile` |
| Need Calculator | `src/pipeline/need_calculator.py` `evaluate_session` |
| Amount helpers | `src/pipeline/goal_math.py` |
| Goal-card inputs | `frontend/src/lib/needEdit.ts` |
