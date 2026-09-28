# FX and PPP data (model V0-22)

Read by `build_calculations_workbook.py` (FX tab). Refresh by replacing the two CSV files.

| File | Content | Source |
|------|---------|--------|
| `currencies_fx.csv` | USD per 1 unit and units per USD, one row per currency (market rate of 2026-09-25) | fawazahmed0 currency-api, npm package `@fawazahmed0/currency-api` version 2026.9.25 |
| `countries_ppp.csv` | Country, ISO codes, currency, World Bank PPP conversion factor (GDP, LCU per international $, latest year), 2024 average market rate (LCU per USD), price level ratio (US = 1), flag | PPP: World Bank `PA.NUS.PPP` via github.com/datasets/ppp (`ppp-gdp.csv`). 2024 average rate: mean of the currency-api on the 15th of March–December 2024. Country → currency: github.com/datasets/country-codes |

Price level ratio = PPP ÷ 2024 average market rate. Both are for the same year, so the ratio is not distorted by later exchange-rate moves. Not used (flag set) when the PPP year is before 2023 or the ratio is outside 0.1–3 (currency reforms, hyperinflation).

Checks against World Bank official rates (PA.NUS.FCRF 2024): SGD +0.01%, THB −0.07%, GBP +0.08%, EUR +0.27%, PHP +0.44%, CHF +0.54%, VND +4.0% (January–February 2024 missing from the sample).

In the app the market rate comes from a live feed and is locked on the session; these files are the workbook snapshot.
