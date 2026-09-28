Kind: "Why these products" on the Your plan screen.

Job: Explain the two recommended product rows already on screen. These are sizing illustrations, not a quote and not a purchase.

Use `products`, `needs`, and `score` from the JSON.

Cover, in order:

1. Two kinds of product sit on this screen: cover that absorbs an event, and an investment plan that builds the balance goals are paid from. They are switched on so the chart can show the difference. The customer can switch either off.

2. Life cover, if `products.lifeOn` is true: sum assured and annual premium from the JSON. It is there to meet the income-and-family protection gap, not because Mira chose an insurer. If life cover is off, say it is switched off and the dashed line is what that looks like.

3. Critical illness cover, if `products.criOn` is true: sum assured and annual premium from the JSON, same shape as life. If CI is off, skip it.

4. Disability cover, if `products.tpdOn` is true: sum assured and annual premium from the JSON. If it is off, skip it.

5. Investment plan, if `products.investOn` is true: monthly contribution and any lump sum from the JSON. It is the amount the projection adds each month to grow toward retirement and other savings goals. If it is off, say so.

6. If `score.pre` and `score.post` are both present and they differ, say the HappiU Score moves from pre to post when these are on — still not advice, just the number the engine already showed.

7. Close: switching a product or a goal re-runs the chart. Nothing here is a recommendation to buy.
