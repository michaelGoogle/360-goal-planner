Logic flow and attributes: [Calculations.md](Calculations.md).

## Scenario Visualizer — formulas

GP maps the session after Plan Calculator, and Scenario Visualizer projects
it. The field map is [HU-and-SV-payloads.md](../HU-and-SV-payloads.md). The
year step is in SV (`ProductSavings.setProductValue`,
`AssetBaseClass._setReturnMatrix`, `CashFlowGeneratorV2._setTotalWealth`).
GP does not run it.

**GP code:** `src/sv_payload.py` `build_sv_payload`.

The engine runs the path twice. `preWealth` is the session without the plan.
`postWealth` is the same session plus the Plan Calculator mix
(`planMth`, `planLump`, `planSum`, `planPrem`) for needs that are not in
`plansOff`. If every plan is off, the plan block is omitted.

`svNumSims` defaults to 20 (clamped between 10 and 200). The chart plots the
mean across those paths, so the line can move slightly from run to run.
Employee CPF for a citizen is accrued inside the CPF black box. A foreigner
does not get that accrual.

### What GP sends into a year

Salary is gross annual income, `incomeMonthly × 12`, and grows at
`incomeGrowthRate`. Living spend is `expenseMonthly × 12`.

```
cash contribution        = 0
investment contribution  = max(0, take-home − expenseMonthly)
property return          = max(0, assetReturn + 0.4%)
```

Take-home is gross pay minus employee CPF. The investment contribution is
that monthly surplus; Scenario Visualizer adds the figure once a year, with
no further ×12.

The mortgage, when `mortgage` > 0, is a 20-year loan repaid by a level
annual instalment that clears it, interest included:

```
rate       = loanRate
instalment = round(mortgage × rate / (1 − (1 + rate)^−20))
           = round(mortgage / 20)                        if rate = 0
```

**GP code:** `goal_math.annual_loan_payment`. It is the annual form of the
monthly payment the report uses (`monthly_loan_payment`), because Scenario
Visualizer steps the loan once a year.

A stress event at slider year `n` is applied at engine year `n + 1`. Death
zeros salary. A market crash haircuts invested assets. A currency shock
haircuts liquid assets. Hospitalisation is a hospital bill. Long-term care
is an expense span. The slider value is the size of that hit.

### Cash and the risky holdings

`cash` is an asset (`A_SAV`). It compounds at `interestRate` and takes no
contribution. The year's net cashflow goes to a separate savings account
that starts at 0 and grows at the tenant `savingsRate` (1% on helium):

```
cash[t + 1]    = cash[t] × (1 + interestRate)
savings[0]     = 0
savings[t + 1] = savings[t] × 1.01 + netCashflow[t + 1]
netCashflow    = salary − spend − instalment − goal withdrawals − existing life premium × 1.01
                 − investment contribution + CPF payout − employee CPF − plan premiums (post)
```

EDU / SAV / PRP goals leave savings as the full `needAmount` (not inflated)
in the target year.

Investments and the home compound at the rate GP sent (`investmentReturn`,
`property return` above). GP sends `noDeathFlag: true`. On that flag SV
uses the return itself (`growth = 1 + rate`), not a random lognormal draw,
so all `svNumSims` paths are the same:

```
investments[t + 1] = (investments[t] + contribution) × (1 + investmentReturn)
property[t + 1]    = property[t] × (1 + property return)
```

A market crash multiplies every asset by `1 − size` in its year; a currency
shock multiplies liquid assets by `1 − size × 2/3`.

The path runs to age 100 (tenant life expectancy), not the session
`lifeExpectancy`.

### Wealth on the chart

```
wealth = savings + investments + property + insurance value + CPF
wealth = max(0, wealth − remaining mortgage)
```

GP sets `subtractLoanBalances`, so the remaining principal comes off the
stock. The instalment has already left cashflow. Principal still owed
evolves as:

```
remaining[0]     = mortgage
remaining[t + 1] = max(0, remaining[t] × (1 + loanRate) − instalment)
```

With the instalment above, `remaining` reaches 0 in year 20, so the balance
runs down smoothly and there is no step when the loan term ends. The interest
is paid through the instalment, so it is a cost in cashflow. `preWealth` and
`postWealth` are the mean of `wealth` across simulations. The chart floors
each plotted point at 0.

### How a year of spending is paid

The expense-funding panel does not use the chart line. It uses spendable
wealth, which leaves out what cannot be drawn to pay living costs: the home,
CPF, and goal pots funded from assets. The mortgage is set against the home
first, so only debt above the home's value reduces spendable wealth. It is
not floored at 0.

```
spendable = savings + investments + insurance value
            − earmarked goal pots
            − max(0, remaining mortgage − (property + CPF))
```

Active income pays first, then passive income (including payouts), then a
draw on savings. What is still unpaid is the shortfall.

```
active    = min(spend, active income)
passive   = min(spend − active, passive income)
draw      = max(0, spend − active − passive)    while wealth is still positive
shortfall = spend − active income − passive income
                                              once wealth has run out
```

Here "wealth" is the mean spendable wealth. On the year it crosses from
positive to negative, the shortfall is the negative wealth, and the savings
draw is reduced by that same amount. A large home therefore no longer hides a
cash shortfall: the panel shows one as soon as liquid money runs out, even
while the chart line is still above 0.

**SV code:** `CashFlowGeneratorV2._setTotalWealth` (`spendableWealth`) and
`_setExpenseFunding`. `preAvailableWealth` / `postAvailableWealth` in the
response are unchanged and still include the home, because the GP chart
plots them.

### CPF inside SV

For citizens and PRs (`region` `R_SGP`), SV builds CPF from salary with no
opening balances. The contribution wage is salary capped at S$96,000 a year.
Total and employee rates, and the OA / SA / MA split, go by age band. OA
earns 2.5%, SA and MA 4%. Contributions stop at retirement (or at 70 if
retirement is later). At the payout age (65, or retirement if later):

```
RA          = OA + SA + max(0, MA − 63,000)      (MA is capped at 63,000 from then)
multiple    = min(3, floor(RA / BRS))            BRS = 2023–2027 table × 1.03 a year
CPF LIFE    = BRS × multiple is moved out of RA; monthly payout from the table × (1 + 7% × deferral years)
```

RA and the CPF LIFE pot then grow × 1.04 a year, and the payout is paid
into savings. The employee share of contributions leaves savings.

For anyone older than 66, SV's payout index is negative, so the arrays wrap
and RA shows up in year 0. The workbook copies this (Discrepancies row 8).

### The workbook tab

The **Scenario Visualizer** tab in the workbook rebuilds that one path year
by year from the effective session: salary, spend (with the instalment and
goal withdrawals), CPF accounts, cash, investments, home, savings, the
mortgage balance, plan pots, and pre / post wealth. It equals SV for every
persona (`excel_check.py`). Crash, currency, inflation, income and expense
events are orange inputs. Life events (death, CI, hospital, care, wedding,
newborn) are not on the tab yet.

**Twin:** `docs/calculations/deterministic_engines.py` `twin_sv`.

### Sensitivity

The headline is the year-by-year path (`preWealth`, `postWealth`), and
whether it stays above 0. The line is the mean of

```
savings + investments + property + insurance + CPF − remaining mortgage
```

The rank below is from that stock and from the yearly cashflow, not from a
measured tornado. A High attribute moves the level or the slope more than a
Low one.

| Rank | Attribute | Moves | Why |
|------|-----------|-------|-----|
| High | `cash`, `investments`, `property` | level of the whole path | Starting stocks. The home is often the largest piece and stays on the line. |
| High | `mortgage` | level and slope | Remaining principal is subtracted every year. The annuity instalment also leaves cashflow for 20 years. |
| High | `incomeMonthly`, `expenseMonthly` | slope | Surplus `max(0, take-home − expenseMonthly)` is added to investments every year. Spend is also the living-cost outflow. |
| High | `investmentReturn` | slope | Compounds investments, including that yearly surplus. |
| High | `assetReturn` | slope | Compounds the home (`assetReturn + 0.4%`). A large house dominates later years. |
| High | `ageOfRetirement` | slope after that age | Salary stops. Spend continues. Surplus turns negative unless other income or the plan replaces it. |
| High | `planMth`, `planLump`, `planPrem` | `postWealth` only | Contributions add to the plan pots. Premiums leave cashflow. Omitted when every plan is in `plansOff`. |
| High | crash, death (when on) | the years they hit | A crash haircuts invested assets. Death zeros salary. Either can dominate that year and every year after. |
| Medium | `interestRate` | slope | Compounds `cash`, which is usually smaller than the house and the investment pot. |
| Medium | `loanRate` | level and slope | Sets the annuity instalment, so a higher rate means more cash out each year for 20 years. The balance still reaches 0 at year 20. |
| Medium | `incomeGrowthRate` | slope | Grows gross salary until retirement. |
| Medium | `inflationRate` | slope | Grows living spend. |
| Medium | `residency` | slope | Citizens accrue CPF from salary. A foreigner does not. |
| Medium | `endAge` / `lifeExpectancy` | how long the line runs | Longer horizon lets rates and surplus compound further. |
| Medium | `planSum` | `postWealth` when an event pays | Sum assured is a payout, not a starting stock. On a quiet path it barely moves the line. |
| Low | `needAmount`, `have`, `gap` | almost none | The chart is a cashflow stock. Need figures are not added to wealth. Protection needs only tag the home for a sale on death, CI, or disability. |
| Low | `riskProfile`, `priority` | none on the path | Not used by the year step. |
| Low | `svNumSims` | noise | The plotted line is a mean. |

`preWealth` does not move when the plan changes. The pre-to-post step is
the Plan Calculator mix. A higher monthly surplus, or a higher return on
the house and on investments, moves the far end of the line more than the
same change in cash interest.
