Logic flow and attributes: [Calculations.md](Calculations.md).

## Need Profiler — formulas

Full write-up: [People-like-you-and-needs.md](../People-like-you-and-needs.md) §4.

**Code:** `src/pipeline/need_profiler.py`, weights in `src/pipeline/prompts/Need_profiler.json`, FX in `src/fx.py`.  
**No LLM.** Weighted scores, scaled 0–10, then four UNIFIED types are enabled.

GP calls `run_need_profiler(top_n=4)`. `select_unified_top` **ignores** `top_n` and always returns **two protection + N_RET + one other growth**.

Twelve AI labels are scored. Only these map into UNIFIED types GP shows:

| Profiler need | UNIFIED |
|---------------|---------|
| Life Protection | `N_INC` |
| Critical Illness | `N_CRI` |
| TPD (JSON label Disability) | `N_TPD` |
| Hospitalisation | `N_HOS` |
| Retirement | `N_RET` |
| Education | `N_EDU` |
| General Savings | `N_SAV` |
| Personal Accident | `N_PAC` (model V0-16) |

**Model V0-16 (Excel, not yet code)** — naming and codes in [Dictionary.md](Dictionary.md):

- **Farewell is dropped**: not scored, and min–max scaling runs over the 11 remaining labels.
- **Home, Car and Travel Protection are parked** as coverage needs `N_HOM`, `N_CAR`, `N_TRV`: scored and given a priority, no calculator.
- **Personal Accident is a calculator** (`N_PAC`) and joins the protection pick (tie-break order INC, CRI, TPD, HOS, PAC).
- **Home purchase (`N_PRP`) is separated from Home Protection.** No profiler label scores home purchase, so `N_PRP` is never switched on automatically; the customer switches it on. The growth pick is `N_EDU` vs `N_SAV`, and the home-ownership SAV ↔ PRP swap is removed.

Code today: Home Protection maps to `N_PRP`, an owner's `N_SAV` is swapped to `N_PRP`, and personal accident, motor, travel and farewell are scored but never become UNIFIED rows.

Each need score is `Σ (need_weight × option_weight)`. Income, expense, assets, and liabilities stay **local on the session**. For scoring they convert to **PPP-USD** (`local × USD per 1 local ÷ relative price level`, model V0-22; the FX tab shows that combined rate as `FX_pppUsdPerLocal` since V0-23) and then use the **USD option-weight bands** in `Need_profiler.json` (`lt` cut-overs). People Like You does not speak USD.

Starter Income bands (monthly PPP-USD, pending sign-off): below 1,000 → 4; 2,500 → 3; 5,000 → 2; 10,000 → 1; else 0. Examples at the V0-24 snapshot: S$5,000 × 0.78162734 ≈ 3,908 PPP-USD → weight **2** (Singapore's price level is 1, the base). S$20,000 ≈ 15,633 → weight **0**. 5,000 VND × 0.0000836 ≈ 0.42 PPP-USD → weight **4**, where 0.0000836 is the market rate 0.0000385 divided by Vietnam's relative price level 0.4602. Dividing by the price level is what keeps the bands comparable across countries; market FX alone would not.

**Known limitations (scoring redesign may be required):**

- People Like You lifestyle/ward/sports strings (`Basic|Comfortable|Luxurious`, `Single|Double|Ward`) are mapped to profiler options (`frugal|stress-free|only the best`, `A|B`) as of V0-24: Basic → frugal, Comfortable → stress-free, Luxurious → only the best; Single → A, Double / Ward → B; adventurous or high-risk sports → Adventurous, none → 0, any other sport → Life style.
- Existing Life / CI / hospital / disability cover is hard-coded **0**. Car / home / travel have factor weights but no matching `weight_options` labels, so they add 0. Parked: wire policies into `Existing*Coverage` (Calculations.md Open issues).

GP `priority` = **5** if `weightageScore > 7`, else **3**. If the profiler is down, GP enables `{N_INC, N_CRI, N_RET}` plus `N_EDU` when there are dependants or `N_SAV` otherwise, with `needAmount = 0`. Home purchase is not part of the fallback. The Excel workbook does not simulate a 503.

---
