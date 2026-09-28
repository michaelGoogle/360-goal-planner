Logic flow and attributes: [Calculations.md](Calculations.md).

## Need Calculator — formulas

Full write-up: [People-like-you-and-needs.md](../People-like-you-and-needs.md) §5.

**Code:** `src/pipeline/need_calculator.py` (`evaluate_session`).  
**HTTP:** `POST /v1/predict` (first fill) and `POST /v1/needs` (every later input change).

There is **one** engine. The UI sends slider and money inputs; it does not
recompute amounts.

GP sets `existing` from policies (protection). Wealth `existing` stays 0
until the customer tags investments (`need_existing`). Cash is not allocated.
CPF is **not** in the retirement pot (private retirement only). Session inflation (default
**2.3%**) and `investmentReturn` (workbook fallback **4.2%**) feed the
calculator — not a fixed 3%. Lifestyle spend on Your Money cannot be 0.

Lifestyle (share of **today’s expenses**): Frugal **75%**, Stress free
**100%**, Only the best **125%** (default Stress free). Retirement age
defaults to **65**. Years in retirement: **`lifeExpectancy − retAge`** (LE capped at 99; missing or ≤ 0 → 85).

Every non-retirement formula below follows the **TFM_2604 Needs Calculator
workbook** (`Input Output` rows 62–95). GP keeps the Excel formula *shapes* but
uses **session rates** rather than the workbook's per-country rate table. From
model V0-15 it runs in the **system currency, USD** ([Currency.md](Currency.md)):
inputs convert from the user currency, the formulas below run in USD with USD
constants, and results convert back and round in the user currency. There is
no country-of-study or country-of-treatment lookup.

Two annuity conventions, because the workbook is not consistent: life and
retirement use an ordinary annuity, critical illness and disability an
annuity-due.

```
a(r, n)    = (1 − (1+r)^(−n)) / r            ordinary — first payment discounted
aDue(r, n) = (1 − vⁿ) / (1 − v), v = 1/(1+r)  annuity-due — first undiscounted
supportYears(age) = min(max(10, 50 − age), 25)          Excel E12
realReturn = (1 + investmentReturn) / (1 + inflation) − 1    (floored at 0)
T = retAge − age
n = lifeExpectancy − retAge          (LE capped at 99)
annualSpend = expenseMonthly × 12 × lifestyleRate
```

| Type | `needAmount` |
|------|----------------|
| **N_RET** | `annualSpend × (1+realReturn)^T × a(realReturn, n)` — lump **at retirement** |
| **N_INC** (Excel `C64`) | `bequest + liabilities + expenseMonthly × 12 × a(realReturn, dependYears)` — driven by **spend**, not income. `dependYears` defaults to `supportYears(age)`, `liabilities` to the mortgage, `bequest` to 0 |
| **N_CRI** (Excel `C73`) | `incomeReplaceMonthly × 12 × aDue(realReturn, CRI_YEARS) + CRI_COST` — `CRI_YEARS` 3 |
| **N_TPD** (Excel `C82`) | `incomeReplaceMonthly × 12 × aDue(realReturn, TPD_YEARS) + TPD_COST` — `TPD_YEARS` 5 |
| **N_HOS** (Excel `C91`) | `incomeMonthly × 6` |
| **N_LTC** (model V0-19) | `LTC_COST × aDue(realReturn, careYears)` with `careYears = lifeExpectancy − ltcStartAge` — `LTC_COST` USD 129,000 a year (nursing home), `ltcStartAge` default 80 (front-end input). Today's money, have = 0. |
| **N_PAC** (model V0-16, agreed V0-18) | `incomeReplaceMonthly × 12 × aDue(realReturn, PAC_YEARS) + PAC_COST` — `PAC_YEARS` 1, `PAC_COST` USD 62,530.19 (the S$80,000 personal-accident stress event). |
| **N_EDU** (Excel `F73`) | `EDU_COST × (1 + inflation)^(targetYear − thisYear)` — one total course cost, no course-years or children multiplier |

Default target years (model V0-26): each wealth goal has its own, set from the customer's age — `N_EDU` the year they turn `EDU_TARGET_AGE` 50 (children leave home at 20, born when the parent is 30; already older → next year), `N_SAV` at `SAV_TARGET_AGE` 40 (next car / investment) but never shorter than 5 years, `N_PRP` at `PRP_TARGET_AGE` 33 (3 years after marriage at 30) but never shorter than 3 years.

| **N_SAV** / **N_PRP** | customer `needAmount` if already `> 0`; else **1×** / **5×** annual income (GP-only; the workbook has neither) |

Constants (USD, recalibrated in V0-24 at the snapshot SGD rate 0.78162734): critical illness **3 years + USD 156,325.47** treatment, disability **5 years + USD 156,325.47**, hospitalisation **6 months** of income, education **USD 58,622.05** total (= S$200,000 / S$75,000 at that rate, so Singapore is unchanged). All inputs are in USD when these are added, so a VND session no longer adds 200,000 VND. Education discounts at **inflation**, not the real return, matching the workbook. The workbook's `Ward A/B Cost`, `Private Factor` and Farewell (funeral cost) columns are deliberately not implemented.

Amounts are rounded to whole units of the user currency, after converting back from USD.

Parameter names follow [Dictionary.md](Dictionary.md) from model V0-16 (`CRI_COST`, `HOS_MONTHS`, `EDU_COST`, `INC_SUPPORT_*`, `RET_LIFESTYLE_*`, `SAV_INCOME_MULT`, `PRP_INCOME_MULT`).

Sample profile, **as the code behaves today** (age 42, S$6,800/mo income, S$4,000/mo spend, S$200,000 mortgage): N_INC **634,401** (checked against `evaluate_session`), N_CRI **440,363**, N_TPD **593,390**, N_HOS **40,800**. The authoritative expected values are the 50 persona fixtures in `GP/tests/fixtures/model_v0_24/`.

### Longevity stress R_LON (model V0-18)

`N_RET` is re-computed with `n = LON_AGE − retAge` (`LON_AGE` 99) and shown
beside the base need as need, gap and extra need. It does not change the
plan. Example P03: 23 → 34 years in retirement, need 1,633,487 → 2,201,580
(extra need 568,093). The same block shows `N_LTC` with care until 99
(P03: 8 → 19 care years, 1,239,064 → 2,670,660).

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

`cash` is never allocated to a need. Investments stay in one pot and count
as `existing` only when the customer tags an amount, in order `N_RET`,
`N_EDU`, `N_SAV`, `N_PRP`. A later need can take only what is left. Later
retirement shortens `n` and grows have for more years, so the gap falls.

---

## One need-amount model

`POST /v1/predict` and `POST /v1/needs` call the same `evaluate_session`.
Pencil edits do not switch formula set. There is no second amount engine
(`compute_need_amounts` was removed). Suggested plan sizing
(`planProducts.ts`) still runs in the UI and is not this calculator.

---
