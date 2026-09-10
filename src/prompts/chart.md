Kind: "Explain this chart" on the Your plan screen.

Job: Read the projection the customer is looking at. Every figure must come from `chart`. This is not a forecast. It is arithmetic on the rates under Assumptions.

Cover, in order:

1. The chart is their money projected from `chart.startAge` to `chart.endAge` — one point for every year. Not a forecast.

2. Branch on `chart.view`:
   - `wealth`: net wealth, everything they own less everything they owe, year by year. When `chart.plansOn` is true, the solid line is with the plan applied and the dashed one without it. Speak `withPlanEnd` by the end age, and `withoutEnd` if it differs. Then the number worth watching: `lowest` — the thinnest their position ever gets, what a bad year would have to eat through. When `plansOn` is false, this is the path without the recommended plan — say that, and that Apply this plan switches it.
   - `cash`: cashflow. Money coming in above the line, money going out below it, one bar per year. While the bars above are longer they are adding to what they have. Where that reverses they are living off it — retirement on this chart. If `chart.plansOn` is true, this is with the plan (premiums out, payouts in). If false, this is without the plan — say that, and that Apply this plan includes those.
   - `exp`: expense funding. What pays for each year of spending, and the year that stops being enough. The diagnostic behind the net wealth line. If `chart.plansOn` is true, this is with the plan. If false, this is without it — say whether turning Apply this plan on can shrink the shortfall.
   - `sav`: savings. Cash and invested portfolio together, building through working years and drawn down through retirement.

3. Stress events in `events` that are on. If any are on, say the projection already includes the dent they make. If none, they can switch one on — a market crash, six months out of work, a critical illness — and watch where the line bends.

If `chart.ready` is false, say the projection is still running or did not return a path, and stop. Do not invent an ending wealth figure.
