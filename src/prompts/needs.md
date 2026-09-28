Kind: "Explain your goals and needs" on the Your score screen.

Job: Identify the goals and needs on the right of this screen, where they come from, and the gaps. Do not talk about HappiU. Do not talk about a plan, products, or how to close the gaps — that is the next screen.

Use `needs`, `you`, and `ratios` from the JSON.

Cover, in order:

1. Start with why these goals and needs are selected for people like `you.firstName` — a demographic cohort, not a personalised recommendation. Examples of that "why", then continue in this direction for whichever needs are enabled:
   - Retirement: they do not (and cannot) work until life expectancy, so they need a plan for the years after work.
   - Critical illness: not being covered can be extremely costly; an average cancer treatment can run beyond S$100,000 and last years.
   - Property: owning a home can cut housing cost in later life and build an asset.
   Keep this as explanation, not advice. Do not invent numbers that are not in the JSON.

2. Walk the enabled needs in the JSON, largest `gap` first. For each, say the `label`, whether it is fully funded or how much is short. For the largest one or two shortfalls, also say how much they have (`have`) and how much is needed (`need`).

   For `gap`, `have`, and `need`: say the exact JSON integers (drop cents only). Never round to one-decimal millions. 2478589 is "two million four hundred and seventy-eight thousand five hundred and eighty-nine dollars", not "two point seven million". Each need row also has `gapSpoken` / `haveSpoken` / `needSpoken` — prefer those strings.

3. If some enabled needs are fully funded, say so. If none are short, say every switched-on need is fully funded.

4. Optionally: money-health checks in `ratios` sit under the list. If some are outside the recommended band, name those `name`s. If all are inside band, skip this beat.

5. Close: they can tap a line or the pencil to revise a goal or need that does not apply. This screen only identifies the goals, the needs, and the gaps.
