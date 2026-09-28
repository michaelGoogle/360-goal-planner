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

Cash is the savings stock. It starts at `cash` and then compounds at the
certain rate `interestRate`, plus that year’s net cashflow (salary, spend,
the investment contribution, mortgage instalments, plan premiums on the post
path, and insurance cashflows):

```
savings[0]     = cash
savings[t + 1] = savings[t] × (1 + interestRate) + netCashflow[t + 1]
```

Investments and the home are not certain. Each year multiplies the holding
by a lognormal return around the rate GP sent (`investmentReturn` for
investments, `property return` above for the home):

```
growth = exp( (mu − ½ × volatility²) + volatility × Z )
```

`Z` is the random normal draw for that simulation and year. A percentage
stress event multiplies `growth` by `1 + impact / 100` on the years it
covers.

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

**Workbook (V0-14):** Scenario Visualizer tab, columns `SPENDABLE pre` /
`SPENDABLE post` and the result “first age spendable wealth < 0”. The
workbook sets earmarked goal pots funded from assets to 0 (open question).
On the post path the plan pots count as insurance value.

**SV code:** `CashFlowGeneratorV2._setTotalWealth` (`spendableWealth`) and
`_setExpenseFunding`. `preAvailableWealth` / `postAvailableWealth` in the
response are unchanged and still include the home, because the GP chart
plots them.

### Personal stress events (model V0-21)

Death, critical illness, TPD, personal accident, hospitalisation, long-term care, wedding and newborn now run on the Scenario Visualizer tab when switched on. Size and timing come from Assumptions (`R_xxx_SIZE` in USD, `R_xxx_WHEN` as an age, or years from today for wedding and newborn). The cost is converted to user currency and grown with the spend index; it leaves savings in that year (a new "stress events cost" column). Death also stops salary and the CPF wage from that age. Long-term care costs every year from the LTC start age to the year before the session's life expectancy, the same years as `N_LTC`.

P03 with every personal event on: spendable wealth turns negative at 45 (before the plan) and 50 (with the plan).

The path now ends at `LON_AGE` 99 (GP sends it; was 100).

### Longevity stress R_LON (model V0-18)

Scenario Visualizer already runs every path to age 100, with spending in
every year. The chart just stops at `endAge` (85). `R_LON` moves the chart
horizon to `LON_AGE` (99), so the customer sees whether wealth, and
spendable wealth, still stand at 99. It does not change the path itself.
The Need Calculator shows the matching `N_RET` need and gap at 99 beside
the base need; the plan is not re-sized.

P03 (model V0-18): wealth with the plan S$5.35m at 85 and S$6.47m at 99;
spendable wealth S$1.48m at 85 and S$1.19m at 99. `N_RET` need S$1.63m at
85, S$2.20m at 99 (+S$568k).

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
