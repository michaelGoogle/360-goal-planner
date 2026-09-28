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
| Disability | `N_TPD` |
| Hospitalisation | `N_HOS` |
| Retirement | `N_RET` |
| Education | `N_EDU` |
| General Savings | `N_SAV` |
| Home Protection | `N_PRP` |

Personal accident, motor, travel and farewell are scored but never become UNIFIED rows.

Each need score is `Σ (need_weight × option_weight)`. Income, expense, assets, and liabilities stay **local on the session**. For scoring they convert with the FX table (`usd = local × USD per 1 local`) and then use **USD option-weight bands** in `Need_profiler.json` (`lt` cut-overs). People Like You does not speak USD.

Starter Income bands (monthly USD after FX, pending sign-off): below 1,000 → 4; 2,500 → 3; 5,000 → 2; 10,000 → 1; else 0. Example: S$5,000 × 0.74 ≈ 3,700 USD → weight **2**. 5,000 VND × 0.000038 ≈ 0.19 USD → weight **4**. S$20,000 × 0.74 ≈ 14,800 → weight **0**. Market FX is not purchasing-power parity.

**Known limitations (scoring redesign may be required):**

- People Like You lifestyle/ward/sports strings (`Basic|Comfortable|Luxurious`, `Single|Double|Ward`) do not match profiler options (`frugal|stress-free|only the best`, `A|B`). Those flags add 0.
- Existing Life / CI / hospital / disability cover is hard-coded **0**. Car / home / travel have factor weights but no matching `weight_options` labels, so they add 0.

GP `priority` = **5** if `weightageScore > 7`, else **3**. If the profiler is down, GP enables `{N_INC, N_CRI, N_RET, N_PRP or N_SAV}`, or `{N_INC, N_CRI, N_RET, N_EDU}` when there are dependants, with `needAmount = 0`. The Excel workbook does not simulate a 503.

---
