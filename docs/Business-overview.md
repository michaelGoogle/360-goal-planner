# 360-Goal Planner — business overview

## 1. What it is

360-Goal Planner (GP) is a **three-minute, no-sign-up** customer journey. A
person answers a little about themselves; the app estimates where they stand
today, scores how well what they hold covers what their life needs (**HappiU**),
and shows a year-by-year picture of wealth they can test.

The UI brand is **FinPlan360**. Engines are the existing suite services — GP
only orchestrates them.

## 2. Where it sits among the 360F services

| Service | Role |
|---------|------|
| **Fund registry (FM)** | Fund data; optional HeyGen plan-report snapshot. D2C Estimate no longer calls FM. |
| **HappiU (HU)** | Stochastic well-being score (`preHappiU` / `postHappiU`) |
| **Scenario Visualizer (SV)** | Pre / post wealth and cashflow paths |
| **360-Goal Planner (GP)** | **D2C UI + BFF** that maps a session into those three |
| Advisor Narrator (AN) | Advisor-facing HU/SV prose (not used by GP; GP has its own Mira prompts) |

Portal card: suite landing page → compose **8069** / WAN **8469**.

## 3. Customer journey

| Step | Screen | What the customer does | What happens |
|------|--------|------------------------|--------------|
| Start | Intro | Hear what they get, then start | No engine call |
| 1 | About you | One sentence (speak/type) or a classic form; optional statements | `POST /v1/parse-sentence` fills fields |
| 2 | Your money | Correct estimated income, spend, balances, cover | `POST /v1/predict` (People Like You in-process) |
| 3 | Your score | See HappiU, gaps, money-health ratios; risk ability chip (spec) | `POST /v1/score` → HU |
| Plan | Your plan | Switch goals, products, stress events, assumptions | `POST /v1/project` → SV; score again |

Guides on every screen: **Mira** (AI adviser, spoken) and **talk to a human
adviser** (callback form — prototype; nothing is transmitted).

Play buttons (**Hear what you get**, **Explain these figures**, **Explain this
page**, **Explain this chart**, **Why these products**) ask Mira to read the
current screen. Scripts come from `POST /v1/explain`.

## 4. Inputs (business terms)

- **About you:** name, age, gender, residency / nationality, occupation,
  dependants. Optional CPF / bank / policy documents (local parse in the UI).
- **Money:** monthly income and expense, cash, investments, property, mortgage,
  existing policies. Pencil edits stick; provenance is tagged (estimate / you /
  document).
- **Needs:** unified types `N_INC`, `N_CRI`, `N_TPD`, `N_HOS`, `N_RET`, `N_EDU`, `N_SAV`,
  `N_PRP` — enabled flag, need amount, existing cover/savings, gap.
- **Plan knobs:** life cover and investment plan on/off, stress events, rates
  (inflation, income growth, net expected return, …). Net expected return is
  after product costs, seeded from `min(capacity, tolerance)` unless overridden.
- **Risk:** **capacity** from Your money (not People Like You); **tolerance**
  from a 1–5 slider. See [Risk.md](Risk.md).

## 5. Outputs

- A **balance sheet** the customer can correct.
- A **HappiU Score** (0–100) and the gaps behind it.
- A **projection chart** (net wealth, cashflow, expense funding, savings) to a
  chosen age.
- Spoken explanations of those figures (LLM when a key is set).

## 6. What it is not

- Not a second scoring or projection engine
- Not a product quote, application, or purchase
- Not advice to buy, switch, or cancel cover
- Not a replacement for advisor Consoles (HU / SV / PA / PG)

## 7. Trust rules

1. Spoken copy must use figures already on screen (prompts forbid invented
   numbers).
2. “People like you” figures are **estimates** until the customer edits them or
   adds a statement.
3. HappiU and the chart are **simulation means** from HU / SV; they can move
   slightly run-to-run.
4. Human-adviser handover in this prototype confirms locally and stops.

How People Like You, Need Profiler, and Need Calculator are called and
calculated is in [People-like-you-and-needs.md](People-like-you-and-needs.md).
The rest of the formula trail (goal-card edits, suggested plan, budget) is in
[Calculations.md](Calculations.md). What the same session sends to HappiU vs
Scenario Visualizer is in [HU-and-SV-payloads.md](HU-and-SV-payloads.md).
Risk capacity, tolerance, and the mapping to net expected returns are in
[Risk.md](Risk.md). Product decisions and the build sequence are in
[risk-mgmt.md](risk-mgmt.md).
