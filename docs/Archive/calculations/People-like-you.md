Logic flow and attributes: [Calculations.md](Calculations.md).

## People Like You — formulas

Full write-up: [People-like-you-and-needs.md](../People-like-you-and-needs.md) §3.

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

Employee rates (not employer): 20% to age 55, then 18% / 12.5% / 7.5% / 5%. The **S$8,000** cap is the CPF ordinary-wage ceiling from 1 Jan 2026, so the most taken off pay at 20% is **S$1,600**. (S$1,200 was 20% of the old S$6,000 ceiling.)

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
| `liquidAssetValue` / `result.assets` | split `cash = round(assets × 0.15)`, `investments = round(assets × 0.85)` |

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
