Logic flow and attributes: [Calculations.md](Calculations.md).

## HappiU — formulas

GP maps the session and HappiU scores it. The field map is
[HU-and-SV-payloads.md](../HU-and-SV-payloads.md). The score math is in HU
(`UtilityFunctionEnhanced`, `ValueFunction.GoalSecurityValue`,
`HappiUGenerator`). GP does not run it.

**GP code:** `src/hu_payload.py` `build_happiu_payload`, `_budget_line`, `_calc_entry`.

### What GP sends

Salary is gross `incomeMonthly` (monthly). Living spend is
`expenseMonthly`. Cash grows at `interestRate`. Investments grow at
`investmentReturn`. Both contributions are 0. Property and the mortgage are
not sent. Employee CPF is deducted inside HappiU unless `residency` is
Foreigner. `numSims` defaults to 200. `riskProfile` is the suitable band.

Each enabled need keeps the `needAmount` Need Calculator stored. If
retirement is off, GP still sends a synthetic `N_RET`:

```
needAmount = expenseMonthly × 12 × years in retirement
existing   = 0 unless the customer tagged investments to retirement
```

Years in retirement are `lifeExpectancy − ageOfRetirement`.

Retirement living expense on the payload:

```
living = expenseMonthly × lifestyleRate × 12
expectedLivingExpenseInTheCountry = living × 0.75
```

`N_HOS` is renamed `N_HSP`. Critical-illness extras on the payload match Need
parameters: `numYearsIncomeNeeded` = **3** (`CI_YEARS`) and `medicalCost` =
**S$200,000** (`CI_COST`). Life and disability send a funeral lump of
S$10,000 beside `needAmount`.

The recommended benefit on each need is what makes `postHappiU` differ from
`preHappiU`. Before Plan Calculator has written a plan, that benefit is the
need rounded to the nearest S$50,000 and the premium placeholder is S$200.
After Plan Calculator:

```
benefitAmount = planSum          (0 if the need is in plansOff)
budget        = planPrem         (or 200 if planPrem is missing)
growthRate    = investmentReturn on a wealth need, else 0
gfr           = 0.05
annualBudget  = 1500
```

HappiU does not read the product code. It reads `benefitAmount`.

### Four wealth pictures per goal

For each simulated path, HappiU values four pictures against the need `N`
(`needAmount`):

```
base = simulated wealth
pre  = simulated wealth + existing
rec  = simulated wealth + existing + benefitAmount
full = simulated wealth + existing + (needAmount − existing)
```

`existing` is the policy sum assured on a protection need, and cash plus
investments on a wealth need. Protection is scored over the years until the
policy term or death. A wealth need is scored at its target year only.
Negative simulated wealth is floored at 0 before this step. The discount
factor is 1, so a later year is not discounted.

### Value of one picture

`riskProfile` sets how fast extra money above the need stops helping:

```
alpha = 1 + (riskProfile − 1) × 0.5
beta  = 1
whl   = 0.25 × needAmount
```

`w0` is simulated wealth at the first year plus `needAmount` for life,
accidental death, and retirement. For every other need, `w0` is
`needAmount`.

Satiation is `w* = w0 / alpha + N`. Value `v(w)`:

```
v = w0 / (2 × alpha)                 when w > w*
v = (w − N) − (alpha / (2 × w0)) × (w − N)²
                                     when N ≤ w ≤ w*
v = beta × (w − N)                   when whl ≤ w < N
v = beta × (whl − N)                 when w < whl
```

Above the need, more wealth helps less, and past `w*` it does not help at
all. Below the need, the shortfall reduces value in proportion. Below a
quarter of the need, further loss does not reduce it more.

### One goal, then the household

The engine averages `v` across the simulations, then scores the goal as how
much of the way from nothing to fully funded the household is:

```
preGoal  = clamp( (E[v(pre)]  − E[v(base)]) / (E[v(full)] − E[v(base)]) , 0, 1 )
postGoal = clamp( (E[v(rec)]  − E[v(base)]) / (E[v(full)] − E[v(base)]) , 0, 1 )
```

If the full-cover value is not finite, the score is undefined. The same
simulated wealth feeds both scores. `postGoal` moves only because
`benefitAmount` was added.

Goals are then weighted. Priority is the need’s `priority`.

```
floor          = 1 for life, retirement, and critical illness; else 0
logPriority    = max( ln(priority + 1), ln(floor + 1) )
calibration    = 1 for life
               = 2 for retirement
               = 1 / (count of consumption goals) for every other goal
weight         = (logPriority × calibration) / sum of those products
```

```
blended = sum( goal score × weight )
scaled  = blended / (1 + exp(− number of chosen goals))
HappiU  = round(scaled × 100)
```

`preHappiU` uses `preGoal`. `postHappiU` uses `postGoal`. Both are means
over `numSims` paths, so they can move slightly from run to run.

### The workbook tab (no Monte Carlo)

The **HappiU** tab scores the same payload on HU's cashflow rules without
random draws. Each year `k` (age `a = age + 1 + k`) reads q(a) from the HU
tables on the Assumptions tab and turns every event into a probability:

```
alive_k        = Π (1 − q_mortality)(1 − q_accidental death)
P(PTD so far)  = 1 − Π (1 − q_ptd)                 income × (1 − 0.5) from then
P(dismembered) = 1 − Π over earlier years (1 − q_dis)   income × 0 from then
P(CI window)   = 1 − Π over the last Y years (1 − q_ci)  income × (1 − min(1, spend / income))
                 Y = 3 when N_CRI is on, else 5
```

The expected alive path, with `infl_k = (1 + inflationRate)^(k+1)`:

```
income_k   = (1 + incomeMonthly × 12) × (1 + incomeGrowthRate)^(k+1)   before retirement
           + social-security lump in the last working year
           + SAV / PRP amount in the target year (also spent, so net 0)
income_k  ×= 1 − expected cut (CI + PTD + dismemberment above)
spend_k    = expenseMonthly × 12 × infl_k        (× 0.75 after retirement)
medical_k  = −200,000 × infl_k × q_ci − 444,000 × infl_k × P(first PTD)
savings    = max(cash, 1), then × (1 + interestRate) + income − spend − goals + medical
equity_t   = investments × e^(mu t), mu = max(1%, investmentReturn)
W_t        = max(0, equity + savings)           life and retirement goals
C_t        = max(0, income − spend)             every other goal
```

Each goal is scored as above, with the average over simulations replaced by
a survival-weighted sum: protection over years 1 … term − 1 (term 10 + 1 in
the plan; off-plan 10 dependent years for life, age 75 for CI / TPD /
hospital), a wealth goal at its target year only. Death cash flows are left
out because HU does not score dead paths. A goal whose denominator is 0
scores 1 and is flagged.

Scores come within a few points of live HU (P04: tab 87, live 82 on 10,000
draws). HU returns an error for retirees who hold investments; the tab
scores them and sets a flag.

**Twin:** `docs/calculations/deterministic_engines.py` `twin_hu`.

### Sensitivity

The headline is the integer 0–100. A goal’s score is how much of the way
from nothing to fully funded `existing` plus simulated wealth already is,
against `needAmount`. The household number then weights retirement twice as
heavily as life, and life more than the other goals.

The rank below is from that algebra, not from a measured tornado. A typical
edit of a High attribute moves the score more than the same kind of edit of
a Low one.

| Rank | Attribute | Moves | Why |
|------|-----------|-------|-----|
| High | `needAmount` on `N_RET`, then `N_INC` | `preHappiU` and `postHappiU` | `N` is the reference point. Retirement has calibration 2; life has calibration 1. A larger need with the same `have` lowers the ratio. |
| High | `cash`, `investments`, policy sums (`have`) | `preHappiU` and `postHappiU` | Added as `existing` on every wealth need, and as cover on protection. They also start simulated wealth. |
| High | `expenseMonthly` | both | Sizes `N_RET` and `N_INC` (spend-driven). Also the living-expense line HappiU stores on retirement. |
| High | Which needs are enabled, and `priority` | both | Changes the blend and the sigmoid. Switching retirement off still sends a synthetic `N_RET`, so that goal does not leave the score. |
| High | `planSum`, `plansOff` | `postHappiU` only | `benefitAmount` is the only extra in `rec` versus `pre`. `plansOff` sets that benefit to 0. |
| Medium | `incomeMonthly` | both | Sizes `N_CRI`, `N_TPD`, `N_HOS`, `N_SAV`, `N_PRP`, and is the salary in the simulation. Those goals share the leftover weight, so they move the household number less than spend does. |
| Medium | `age`, `ageOfRetirement`, `lifeExpectancy` | both | Change years to the goal and years in retirement, which resize `needAmount` and the path HappiU simulates. |
| Medium | lifestyle on retirement | both | Scales retired spend inside `needAmount` (75% / 100% / 125%). |
| Medium | `riskProfile` | both | Sets `alpha`. It changes how fast money above the need stops helping. It moves the score most when the household is near the need, not when it is far below the floor or already saturated. |
| Low | `investmentReturn`, `interestRate`, `inflationRate`, `incomeGrowthRate` | both | Grow the simulated stocks. They do not change `needAmount` or `existing` on this call. HappiU also sends contribution 0 on cash and investments, so surplus is not saved the way it is on the chart. |
| Low | `numSims` | both | Noise around the mean, not the mean itself. |
| None | `property`, `mortgage`, `assetReturn`, `loanRate` | — | Not sent. |
| None | `planMth`, `planLump` | — | HappiU does not read them. A wealth need with no `planSum` uses `needAmount` rounded to S$50,000 as `benefitAmount`. |

`preHappiU` does not move when the plan changes. The pre-to-post step is
only `benefitAmount`. Closing a large retirement or life gap with
`planSum` therefore moves `postHappiU` more than the same sum on a
down-weighted consumption goal.
