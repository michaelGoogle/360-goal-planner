Logic flow and attributes: [Calculations.md](Calculations.md).

## System currency — USD

*Model V0-15 (Excel and docs). Code follows from V0-25.*

FinPlan360 is country agnostic. **USD is the system currency.** The customer
enters and sees amounts in their own **user currency**. Every calculator and
every validation runs in USD.

```
user currency ──× usdPerLocal──► USD ──► calculator + validations (USD parameters)
      ▲                                              │
      └──────────── ÷ usdPerLocal, round ◄───────────┘
```

`usdPerLocal` is USD for 1 unit of the user currency (FX tab).

### Rules

1. **One rate per session.** In the app, `usdPerLocal` comes from an FX feed
   and is stored on the session when the session starts. A customer's needs do
   not move overnight because the rate moved. The rate changes only on a
   deliberate refresh.
2. **Unknown currency is an error.** No fallback to SGD. The workbook shows
   `#N/A` on every calculator.
3. **Fixed amounts are USD.** They sit on the Assumptions tab and are the only
   money constants in the model. They are calibrated from the Singapore values
   at the FX snapshot rate (SGD 0.78162734, 2026-09-25), so Singapore results
   do not change. V0-24 recalibrated them after the snapshot rate moved from
   0.74, which is why the USD figures below are not the V0-15 ones.
4. **Round in user currency, after converting back.** Whole-unit results
   (need amounts, home value) round to 1 unit. Step rounding uses a step
   derived from the USD step: `USD step ÷ usdPerLocal`, then the nearest
   1, 2 or 5 × 10^k. SGD gives the V0-14 steps (1,000 / 50 / 10 / 100,000 /
   50,000). VND gives 20,000,000 / 1,000,000 / 200,000 / 2,000,000,000 /
   1,000,000,000.
5. **Ratios and rates do not change with currency.** Spend shares, annuities,
   growth rates and the free-budget share give the same answer in any
   currency. Converting to USD and back only matters for fixed amounts and
   rounding.

### Fixed amounts (USD)

Values as of V0-24. The authoritative list is the Assumptions tab; the export
in `GP/tests/fixtures/model_v0_24/parameters.json` carries the same numbers
with their unit, currency and code source.

| Parameter | USD | Calibrated from (SGD) | Used by |
|-----------|-----|-----------------------|---------|
| `CRI_COST` | 156,325.47 | 200,000 | Need Calculator `N_CRI` |
| `TPD_COST` | 156,325.47 | 200,000 | Need Calculator `N_TPD` |
| `EDU_COST` | 58,622.05 | 75,000 | Need Calculator `N_EDU` |
| `PAC_COST` | 62,530.19 | 80,000 | Need Calculator `N_PAC` |
| `LTC_COST` (per year) | 129,000 | set in USD | Need Calculator `N_LTC` |
| `propertyLow / Mid / High` | 273,569.57 / 508,057.77 / 664,383.24 | 350k / 650k / 850k | People Like You home seed |
| `propertyIncomeLow / High` (monthly) | 7,816.27 / 15,632.55 | 10,000 / 20,000 | People Like You home seed |
| `lifeRoundUnit` (step) | 78,162.73 | 100,000 | People Like You life cover |
| `lumpRoundStep` / `monthlyRoundStep` (steps) | 781.63 / 39.08 | 1,000 / 50 | Plan Calculator |
| `coverPremRoundStep` (step) | 7.82 | 10 | Plan Calculator |
| `coverSliderPremFloor` | 156.33 | 200 | Plan screen |
| `annualBudget` / `placeholderNeedBudget` | 1,172.44 / 156.33 | 1,500 / 200 | HappiU payload |
| `benefitRound` (step) | 39,081.37 | 50,000 | HappiU payload |
| `MIN_EXPENSE_MONTHLY` (V0-21) | 100 | set in USD | spend floor |
| Stress-event sizes (V0-21) | see Assumptions `R_xxx_SIZE` | S$20k–200k | Scenario Visualizer |

The steps above are the USD figures before `nice_step` rounds them in the user
currency; SGD still gives 100,000 / 1,000 / 50 / 10 / 50,000.

The USD figures can be rounded to “nice” USD numbers later. That is a
product decision and changes Singapore results slightly.

### Country plug-ins

Some rules are country law, not parameters. They are **plug-ins** with one
interface and run in the user currency:

| Plug-in | In | Out | Modules today |
|---------|----|-----|---------------|
| Social security | gross income, age, residency, country | employee contribution, take-home | SG-CPF (`src/cpf.py`); default = no contribution |
| Income anchors (People Like You clamp) | occupation, country | min / max gross income | `income_anchors.json` |

A country without a module uses the default. The rest of the model does not
change when a module is added.

### PPP price level (model V0-22, option B on)

Market rates convert money. They do not say what money buys: USD 156,325 of
treatment costs far less in Hanoi than in Singapore. The price level fixes
that with one number per country, from one public source, refreshed yearly.

```
price level (country, US = 1) = World Bank PPP (LCU per int. $) ÷ 2024 average market rate (LCU per USD)
relative price level           = price level (country) ÷ price level (PPP_BASE_COUNTRY = Singapore)
USD fixed amount used          = USD fixed amount × relative price level
PPP-USD (Need Profiler bands)  = local amount × USD per 1 local ÷ relative price level
```

- **Per country, not per currency.** Germany and Portugal share EUR but not prices.
- **Base country Singapore.** The USD fixed amounts were calibrated from Singapore
  values, so Singapore's factor is 1 and Singapore results are unchanged by PPP.
- **Same year.** PPP and the market rate are both 2024, so later exchange-rate
  moves do not distort the ratio.
- **No usable PPP → market rate.** 59 of 245 countries (no World Bank PPP, PPP
  older than 2023, or a ratio outside 0.1–3 from currency reforms or
  hyperinflation) fall back to factor 1 (option A).
- Examples (US = 1): Singapore 0.60, Vietnam 0.28, Malaysia 0.31, Thailand 0.30,
  India 0.24, China 0.49, Japan 0.62, Germany 0.76, UK 0.85, Australia 0.90,
  Switzerland 1.07. Vietnam relative to Singapore: 0.46.

Data: `fx_ppp/countries_ppp.csv` (245 countries) and `fx_ppp/currencies_fx.csv`
(152 currencies, market rate 2026-09-25). Sources and checks: `fx_ppp/SOURCES.md`.

Check (V0-24, P03 re-entered in VND at the same USD gross income, country
Vietnam; all figures SGD-equivalent). Cost-driven needs follow Vietnamese
prices at the relative price level 0.4602: N_EDU 49,661 vs 107,912 and N_LTC
570,212 vs 1,239,064 are both exactly 46% of the Singapore amount, and N_CRI
344,421 vs 452,382, where only the treatment lump is scaled. Purely
income-driven needs are identical in both sessions: N_HOS 42,840, N_SAV 85,680.

Spend-driven needs come out **higher** in the Vietnamese session (N_INC
1,017,554 vs 874,927; N_RET 2,041,859 vs 1,633,487, exactly 1.25×). That is the
default social-security module behaving as designed, not an FX or PPP effect:
Vietnam has no module, so take-home is gross and spend is 72.5% of the whole
salary instead of 72.5% of salary after 20% CPF.

**Rate update.** The snapshot SGD rate is 0.78162734 (2026-09-25), not the 0.74
of V0-15. V0-24 recalibrated the USD fixed amounts at that rate, so the
Singapore amounts are unchanged again (`CRI_COST` is S$200,000). Between V0-22
and V0-23 the Singapore amounts were 5.3% lower, because the rate had moved
while the USD amounts had not.

### Option A and option B

- **A — market rate (V0-15 to V0-21).** Fixed USD amounts convert at the market
  rate. Simple, no maintenance. In a low-cost country they are too large:
  USD 156,325 of treatment buys far more care in Hanoi than in Singapore, so
  the need is overstated by roughly the inverse of the price level (Vietnam
  0.46, so about 2.2×).
- **B — market rate × price level (on from V0-22, see above).** `priceLevelOn` on
  Assumptions and a price-level column on the FX tab (1 for every currency
  today). Turned on, the USD fixed amounts are multiplied by the country's
  price level. One number per country, loaded from one public source (for
  example the World Bank price-level ratio), not maintained by hand.

### Check (V0-15 workbook)

- Singapore: 8 personas (P01, P03, P06, P09, P12, P23, P26, P48) give the same
  value as V0-14 on every named cell, including the Scenario Visualizer and
  HappiU year tables.
- Currency neutrality: P03 re-entered in VND at the same USD value gives the
  SGD result × rate on every need (for example N_CRI 452,382 SGD =
  8,809,535,983 VND). V0-14 gave 4,914,999,141 VND, because it added
  VND 200,000 instead of S$200,000 of treatment. Education was VND 94,149.
  Plan contributions differ only by the rounding step (VND 1,000,000 ≈ S$51).
