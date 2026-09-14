# 360-Goal Planner — risk capacity, tolerance, and expected returns

How FinPlan360 decides **how much market risk the household can carry**, how
the customer **declares comfort**, and how those two numbers cap **net expected
returns** on the plan calculator.

The product story stays in [Business-overview.md](Business-overview.md). Money
formulas stay in [Calculations.md](Calculations.md). People Like You still
predicts a lifestyle `risk_ability` word; **GP does not use it as displayed
capacity** — see §8 and
[People-like-you-and-needs.md](People-like-you-and-needs.md) §3.1.

If a formula here drifts from code, the file named in each section is the source of truth.

**Status:** live in the Score risk card (`frontend/src/pages/Score.tsx`) and
`frontend/src/lib/riskCapacity.ts`. Product decisions: [risk-mgmt.md](risk-mgmt.md).

---

## 1. What is live today

| Piece | Live behaviour |
|-------|----------------|
| People Like You `risk_ability` | LLM: `conservative` / `moderate` / `aggressive`, mapped to profiles **2 / 3 / 5** in `src/pipeline/people_like_you.py`. Unused by Score. |
| Session | `_apply_plu` **does not** copy that field. `riskTolerance` defaults to **3**. `riskProfile` is `min(capacity, tolerance)`. |
| HappiU | `src/hu_payload.py` sends `session.riskProfile` (the suitable band). |
| Plan net expected return | Seeded from `suggestedNetReturn(min(capacity, tolerance))` unless the customer overrode it. Slider 2.2–10%, green → red, soft ceiling not clamped. |
| Score | Overview chip **Risk ability · {band}**; risk card above the six ratio cards. |

---

## 2. Three quantities (do not mix them)

| Quantity | Whose number | Role |
|----------|----------------|------|
| **Risk capacity** | Calculated from Your money + horizon + dependants | What volatility the **balance sheet** can absorb. Derived, not a free slider. |
| **Risk tolerance** | Customer (v1: 1–5 slider) | What volatility they **say** they can sit with. |
| **Risk required** | Implied by the goal gap at the planning rate | What return would **close the shortfall**. Shown as a shortfall on the plan card, **never** as the assumed rate. |

Suitable band:

```
suitable = min(capacity, tolerance)    // 1–5, PA bands
```

Never take the **maximum**. That would use the looser number to justify more
risk. Never feed **required** return into the assumed rate — that paints over
the gap with a figure the net-return track already marks unlikely (8–10% after
insurance-plan costs).

PA bands (same names and vol brackets as
[`PA/frontend/src/lib/riskBand.ts`](../../PA/frontend/src/lib/riskBand.ts)):

| Profile | Label | Annual volatility |
|---------|-------|-------------------|
| 1 | Low | < 10% |
| 2 | Low-Medium | 10% – 15% |
| 3 | Medium | 15% – 20% |
| 4 | Medium-High | 20% – 30% |
| 5 | High | ≥ 30% |

Copy is **risk ability** / **risk capacity** on the Score card, never “risk
tolerance” for the calculated number, and never “risk appetite” for the
chip.

---

## 3. Where it sits in the journey

```text
Your money   (income, spend, cash, investments, property, mortgage)
    │
    ▼
Your score
    ├── overview chip     “Risk ability · Medium-High”   (PA colour)
    ├── risk card         capacity readout + tolerance slider
    └── ratio cards       six pass/fail money-health checks  (unchanged)
    │
    ▼
Your plan
    └── net expected returns slider
            suggested rate + soft ceiling from min(capacity, tolerance)
```

- Ratios stay **pass/fail** against recommended bands. Risk is **not** a
  seventh ratio.
- The risk card is a **sibling above** “Your financial health ratios”, not a
  row inside `x-rat`.
- The overview chip sits in the HappiU card next to the ratio-attention chip.
  Clicking it opens the risk card (and the ratios accordion if a hard cap
  fired).
- Capacity changes only when Your money (or age / retirement age / dependants)
  changes. Tolerance is the only risk control the customer drags.

---

## 4. Risk capacity

**Code:** `frontend/src/lib/riskCapacity.ts`.  
**Inputs:** same money fields as `frontend/src/lib/ratios.ts`, plus `age`,
`ageOfRetirement` (default 65), `dependents`.

### 4.1 What to include and exclude

| Use | Formula | Session fields |
|-----|---------|----------------|
| Liquidity months | `cash / expenseMonthly` | `cash`, `expenseMonthly` |
| Savings ratio | `(incomeMonthly − expenseMonthly) / incomeMonthly` | income, expense |
| Debt service (DSR) | `(mortgage / 240) / incomeMonthly` | same as the ratio card |
| Debt / assets (DAR) | `mortgage / (cash + investments + property)` | same as the ratio card |
| Horizon years | `max(0, ageOfRetirement − age)` | `ageOfRetirement`, `age` |
| Dependants | count | `dependents` |

**Do not use**

- **Investments / net worth** — allocation, not ability. A high ratio means
  they are already taking risk.
- **Occupation / PLU `risk_ability`** — guessed before spend and cash exist.
- **CPF OA / SA / MA** — not emergency cash; do not pad liquidity with them.

Divide-by-zero: treat missing income or expense as a failed liquidity / savings
input (points **1**), not as “unknown → Medium”.

### 4.2 Score each factor 1–5

Use the **value**, not only the ratio card’s pass/fail, so 2.9 months is not
the same as 0.4.

**Liquidity** (months of cash) — heaviest

| Months | Points |
|--------|--------|
| < 1 | 1 |
| 1 – < 3 | 2 |
| 3 – < 6 | 3 |
| 6 – < 12 | 4 |
| ≥ 12 | 5 |

**Savings ratio** (surplus / income)

| Ratio | Points |
|-------|--------|
| < 0 | 1 |
| 0 – < 10% | 2 |
| 10 – < 20% | 3 |
| 20 – < 30% | 4 |
| ≥ 30% | 5 |

**Debt service** (lower is better)

| DSR | Points |
|-----|--------|
| > 50% | 1 |
| 35 – 50% | 2 |
| 20 – < 35% | 3 |
| 10 – < 20% | 4 |
| ≤ 10% | 5 |

**Debt / assets**

| DAR | Points |
|-----|--------|
| > 70% | 1 |
| 50 – 70% | 2 |
| 30 – < 50% | 3 |
| 15 – < 30% | 4 |
| ≤ 15% | 5 |

**Horizon** (years to retirement)

| Years | Points |
|-------|--------|
| < 5 | 1 |
| 5 – < 10 | 2 |
| 10 – < 20 | 3 |
| 20 – < 30 | 4 |
| ≥ 30 | 5 |

**Dependants**

| Count | Points |
|-------|--------|
| 0 | 5 |
| 1 | 4 |
| 2 | 3 |
| 3 | 2 |
| 4+ | 1 |

### 4.3 Weighted average, then hard caps

```
raw = 0.25×liquidity
    + 0.20×DSR
    + 0.15×DAR
    + 0.15×savings
    + 0.15×horizon
    + 0.10×dependants

capacity = round(raw)          // 1–5
capacity = min(capacity, cap)  // hard floors below
```

Round half away from zero to nearest integer, then clamp to 1–5.

Hard caps (apply **after** rounding). The average can look healthy while one
killer metric is broken.

| If this is true | Capacity cannot exceed |
|-----------------|------------------------|
| Liquidity < 1 month | **1 Low** |
| Liquidity < 3 months | **2 Low-Medium** |
| DSR > 50% or DAR > 70% | **2 Low-Medium** |
| DSR > 35% or DAR > 50% | **3 Medium** |
| Horizon < 5 years | **2 Low-Medium** |
| Horizon < 10 years | **3 Medium** |

When several caps fire, take the **strictest** (lowest). The card shows one
reason: the cap that actually bound.

Capacity is **not editable**. To raise it, the customer changes cash, spend,
debt, or retirement age on Your money.

### 4.4 Worked example (42, 2 dependants, retire 65)

Illustrative Your-money shape (same ballpark as a mid-career professional with
the 15/85 cash–investments split and a 55% LTV home):

- Income S$25,000 · spend S$17,485 · surplus S$7,515
- Investments ~S$805,000 · cash ~S$142,000
- Home S$850,000 · mortgage S$468,000

| Factor | Value | Points |
|--------|-------|--------|
| Liquidity | 8.1 months | 4 |
| DSR | 7.8% | 5 |
| DAR | 26% | 4 |
| Savings | 30% | 5 |
| Horizon | 23 years | 4 |
| Dependants | 2 | 3 |

```
raw = 0.25×4 + 0.20×5 + 0.15×4 + 0.15×5 + 0.15×4 + 0.10×3
    = 4.25  →  round 4  Medium-High (20–30% vol)
```

No hard cap fires. Same person with cash cut to **2 months**: liquidity points
= 2, and the cap pins them at **2 Low-Medium** even if DSR and savings still
look excellent. That is the mismatch People Like You’s `aggressive` guess
creates today.

---

## 5. Risk tolerance (v1)

A **1–5 slider**, same PA labels and vol ranges, restyled for the light Score
card (emerald → lime → amber → orange → rose). Not a MAS CKA and not a
drawdown questionnaire.

- Default **3 Medium** until they move it.
- Session: `riskTolerance` plus `riskToleranceTouched` so a later money edit
  does not wipe a choice they made.
- If `tolerance > capacity`, one line on the card: capacity is the binding
  constraint; the plan will not assume a higher band.

---

## 6. Mapping to net expected returns

The plan wealth slider is **net** expected return: fund performance **after**
sales load and typical 2–4% a year wrapper / fund costs. Default **4.2%**.
Track 2.2–10%, green (likely after costs) → red (10% after costs is highly
unlikely). See `frontend/src/lib/assumptions.ts`.

Once wired (this is live):

```
band     = min(capacity, tolerance)
suggest  = suggestedNetReturn(band)     // seeds investmentReturn / investRet
ceiling  = netReturnCeiling(band)       // soft — do not clamp the slider
```

| `min(capacity, tolerance)` | Suggest (net) | Soft ceiling |
|----------------------------|---------------|--------------|
| 1 Low | 3.0% | 4.2% |
| 2 Low-Medium | 3.5% | 5.0% |
| 3 Medium | 4.2% | 5.5% |
| 4 Medium-High | 5.0% | 6.0% |
| 5 High | 5.5% | 6.5% |

High still does **not** suggest 8–10% after ILP costs. The customer can drag
above the ceiling; the green→red track is the warning. Do not auto-move the
rate into the red zone to close a retirement shortfall.

Seed / refresh the suggested rate:

- On first `seedProducts`.
- When capacity or tolerance changes **and** the customer has not overridden
  the rate (mirror `riskToleranceTouched` / a `investmentReturnTouched` flag).

When the rate changes, existing `clampAllWealthToCaps` recalculates lump and
monthly caps.

---

## 7. HappiU

`frontend/src/lib/api.ts` already sends `riskProfile`.
`src/hu_payload.py` already reads it into the policy owner.

Once wired, `riskProfile = min(capacity, tolerance)` whenever money or
tolerance changes. That is what HU receives.

This is the HU utility curvature input (`alpha` from `riskProfile`), not a
portfolio mix. GP still does not call PG `/risk-mapping`.

---

## 8. People Like You `risk_ability`

The prompt still asks for `conservative | moderate | aggressive`. The mapper
still writes `policyOwner.riskProfile` and `result.riskAbility`. GP Estimate
**must not** copy that onto the D2C session as the Score chip.

Leave the LLM field unused, or stop merging it into onboarding — either is
fine as long as capacity comes from §4.

---

## 9. Non-goals

- Not advice to buy, switch, or hold funds
- Not a MAS Customer Knowledge Assessment
- Not PG fund-mix selection
- Not editing capacity without changing Your money
- Not a full tolerance questionnaire in v1 (slider only)

---

## 10. Implementation

Shipped. Formulas in this file; product decisions in [risk-mgmt.md](risk-mgmt.md).
Tests: `frontend/src/lib/riskCapacity.test.ts` (`npm run test:lib`).

v1 does not include a full tolerance questionnaire, PG `/risk-mapping`, editing
capacity without changing Your money, or inflating the assumed rate to close a
shortfall.

---

## Code index

| Concern | Path |
|---------|------|
| Capacity / suitable / return map | `frontend/src/lib/riskCapacity.ts` |
| PA bands (light GP chips) | `frontend/src/lib/riskBand.ts` |
| Session fields | `frontend/src/lib/types.ts` (`riskTolerance`, `riskProfile`, `investmentReturnTouched`) |
| Money-health ratios | `frontend/src/lib/ratios.ts` |
| Score UI | `frontend/src/pages/Score.tsx` |
| Net-return slider | `frontend/src/lib/assumptions.ts`, `pages/plan/CoverCard.tsx` |
| Product seed | `frontend/src/lib/local.ts` `seedProducts` |
| PLU `risk_ability` | `src/pipeline/people_like_you.py` (unused by Score) |
| HU `riskProfile` | `src/hu_payload.py` |
