Logic flow and attributes: [Calculations.md](Calculations.md).

## Plan Calculator — formulas

**Code:** `frontend/src/lib/planProducts.ts`, seeded from `local.ts` `seedProducts`.

A need is **suggested** if it is enabled **and** `needCardGap > 0`. Switching a plan off lists it in `plansOff` (the need can stay on).

### Protection (N_INC, N_CRI, N_TPD, N_HOS)

Default sum assured = the current card gap (rounded).  
Indicative annual premium (**dummy** until a premium-quote calculator API exists):

```
indicative = round((sum × 0.00078) / 10) × 10
default planPrem = indicative
```

That **0.00078** factor is a D2C placeholder, not a quoted tariff. The live
default is the indicative itself, not half of the slider max.

### Wealth (N_RET, N_EDU, N_SAV, N_PRP)

Horizon: years to retirement age, or `targetYear − this year`.  
Rate: session `investmentReturn` on the Plan **net expected returns** slider
(seeded from the suitable risk band; workbook fallback **4.2%** p.a. after
product costs), deflated by session inflation. (`investRet` is the same rate
in percent.) Mapping: [Risk.md](../Risk.md) §6.

Lump and monthly caps are the amounts that, **alone**, grow to the remaining gap:

```
lump_cap     = PV of gap over horizon at real plan rate   (round up to S$1,000)
monthly_cap  = annual PMT to hit gap, / 12                 (round up to S$50)
```

Default monthly (first seed), split across suggested wealth needs:

```
annual_surplus = max(0, (takeHomeMonthly − expense) × 12)
left           = max(0, annual_surplus − protectionPremAnnual)
share          = round(left × 0.5 / 12 / n_wealth / 50) × 50
planMth[type]  = min(share, monthly_cap)
planLump[type] = 0
```

`investMth` / `investLump` on the session are the **sums** of included wealth plans. Chart / HU see those totals, not the per-goal split.

Growth shown on a wealth plan:

```
FV = lump × (1+r)^n  +  FV_annuity(monthly × 12, r, n)
remain = needAmount − have − FV
```

---
