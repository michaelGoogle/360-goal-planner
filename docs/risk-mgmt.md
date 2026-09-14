# GP risk management — product decisions and build plan

Working document for how FinPlan360 **determines risk**, **implements it**, and
**maps it to net expected returns**. Formulas and the worked example live in
[Risk.md](Risk.md). This file keeps the **holistic plan**: why we split
capacity from tolerance, what is live today, and the build sequence.

**Status:** live. Score risk card, capacity closed form, and return mapping
are in the tree. Formula trail: [Risk.md](Risk.md).

---

## 1. Decisions (do not re-litigate in the build)

### 1.1 People Like You is not the source of capacity

Keep People Like You for income, lifestyle, property, and the needs pipeline.
**Stop using LLM `risk_ability`** (`conservative` / `moderate` / `aggressive`
→ profiles 2 / 3 / 5) as what the Score page shows.

That field is guessed from occupation **before** spend, cash, and loans exist.
`_apply_plu` already does not copy it onto the session. Occupation is not an
input to capacity.

### 1.2 Two numbers, one suitable band

| Quantity | Source | Customer can drag? |
|----------|--------|--------------------|
| **Risk capacity** (ability) | Calculated from Your money + horizon + dependants | No — edit cash, debt, spend, or retirement age |
| **Risk tolerance** | 1–5 slider (v1; not a questionnaire) | Yes |
| **Risk required** | Return that would close the goal gap | No — shown as **shortfall**, never as the assumed rate |

```
suitable = min(capacity, tolerance)    // never max
```

The **higher** of the two is unsuitable: it uses the looser number to justify
more risk. An average still softens the constraint. Required return must not
inflate the plan rate (that paints over the gap with 8–10% after ILP costs,
which the net-return track already marks red).

Copy: **risk ability** / **risk capacity** for the calculated number; **risk
tolerance** / **comfort** for the slider. Never call the chip “risk appetite”.

### 1.3 Separate card, not a seventh ratio

Ratio cards stay pass/fail money health (3–6 months cash, 35% DSR, …). Risk
ability has no universal “ok” band.

- **Overview chip** on the HappiU card, next to “N financial health ratios
  need attention”, PA-coloured, e.g. `Risk ability · Medium-High`.
- **Risk card above** “Your financial health ratios” (sibling section, not a
  row in `x-rat`): derived capacity + cap reason; tolerance slider; one line
  if `tolerance > capacity`.

### 1.4 PA bands and colours

Same five labels and vol brackets as
[`PA/frontend/src/lib/riskBand.ts`](../../PA/frontend/src/lib/riskBand.ts):

| Profile | Label | Annual volatility |
|---------|-------|-------------------|
| 1 | Low | < 10% |
| 2 | Low-Medium | 10% – 15% |
| 3 | Medium | 15% – 20% |
| 4 | Medium-High | 20% – 30% |
| 5 | High | ≥ 30% |

PA pills are dark-theme (`text-emerald-300`). GP chips are light (red / green /
amber tags). Keep **names and vol numbers**; restyle hues for the light Score
card (emerald → lime → amber → orange → rose). Portal
[`portal/src/lib/riskBand.ts`](../../portal/src/lib/riskBand.ts) has the same
tracks.

### 1.5 Net expected returns (already live)

The plan wealth slider is **after product costs**, not headline fund return.
Insurance investment plans typically take a sales load (front or back) plus
2–4% a year in fund and wrapper fees. Default **4.2%**. Track 2.2–10%, green →
red by likelihood after those costs. Tooltips sit on every plan slider.
See `frontend/src/lib/assumptions.ts` and `pages/plan/CoverCard.tsx`.

This mapping is live: `suggestedNetReturn(min(capacity, tolerance))` seeds the
slider unless the customer overrode it.

### 1.6 Suggested rate and soft ceiling (spec)

`band = min(capacity, tolerance)`. Default stays 4.2% until seeded. High still
does not suggest 8–10% after ILP costs.

| Band | Suggest (net) | Soft ceiling |
|------|---------------|--------------|
| 1 Low | 3.0% | 4.2% |
| 2 Low-Medium | 3.5% | 5.0% |
| 3 Medium | 4.2% | 5.5% |
| 4 Medium-High | 5.0% | 6.0% |
| 5 High | 5.5% | 6.5% |

Dragging above the ceiling stays **allowed**; do not clamp. The green→red
track is the warning. Do not auto-move the rate into the red zone to close a
shortfall.

### 1.7 HappiU

`session.riskProfile = min(capacity, tolerance)`. That is HU utility curvature
(`alpha`), not a PG fund mix. GP does not call `/risk-mapping`.

### 1.8 Non-goals (v1)

- Not advice to buy, switch, or hold
- Not a MAS Customer Knowledge Assessment
- Not a full tolerance questionnaire (slider only)
- Not PG fund-mix selection
- Not editing capacity without changing Your money
- Not using required return to inflate the assumed rate

---

## 2. What is live today

| Piece | Live behaviour |
|-------|----------------|
| PLU `risk_ability` | LLM conservative / moderate / aggressive → 2 / 3 / 5. Unused by Score. |
| Session | `_apply_plu` does not copy it. `riskTolerance` default **3**. `riskProfile` = `min(capacity, tolerance)`. |
| HappiU | Sends that suitable band. |
| Plan net expected return | Seeded from the band unless overridden. Slider 2.2–10%, green→red, soft ceiling not clamped. |
| Score | Chip **Risk ability · {band}**; risk card above the six ratio cards. |

Capacity formulas, hard caps, and the worked 42 / 2-dependants example:
[Risk.md](Risk.md) §4. Tests: `frontend/src/lib/riskCapacity.test.ts`.

---

## 3. Build sequence (done)

Shipped in `frontend/src/lib/riskCapacity.ts`, `riskBand.ts`, `pages/Score.tsx`,
`local.ts` `seedProducts`, Plan/Assumptions sliders, and `App.tsx` `withRisk`.

v1 still excludes a full questionnaire, PG `/risk-mapping`, editing capacity
without changing Your money, and inflating the assumed rate to close a shortfall.

---

## 4. Files

| Concern | Path |
|---------|------|
| This plan | `GP/docs/risk-mgmt.md` |
| Formula trail | `GP/docs/Risk.md` |
| Capacity / suitable / return map | `frontend/src/lib/riskCapacity.ts` |
| PA bands (light GP chips) | `frontend/src/lib/riskBand.ts` |
| Session fields | `frontend/src/lib/types.ts` |
| Money-health ratios | `frontend/src/lib/ratios.ts` |
| Score UI | `frontend/src/pages/Score.tsx` |
| Net-return slider | `frontend/src/lib/assumptions.ts`, `pages/plan/CoverCard.tsx` |
| Product seed | `frontend/src/lib/local.ts` `seedProducts` |
| PLU `risk_ability` | `src/pipeline/people_like_you.py` (unused by Score) |
| HU `riskProfile` | `src/hu_payload.py` |

---

## 5. Related docs

| Doc | Role |
|-----|------|
| [Risk.md](Risk.md) | Capacity lookups, weights, hard caps, worked example, return table |
| [Calculations.md](Calculations.md) | Live money / plan formulas (rate seeded from the risk band) |
| [People-like-you-and-needs.md](People-like-you-and-needs.md) | LLM still returns `risk_ability`; GP does not use it as the Score chip |
| [Business-overview.md](Business-overview.md) | Journey and inputs |
| [Open-issues-and-tasks.md](Open-issues-and-tasks.md) | Gap #11 done |

