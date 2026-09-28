Logic flow and attributes: [Calculations.md](Calculations.md).

## Budget Calculator — formulas

### What the Plan screen treats as budget

**Code:** `planAfford` in `planProducts.ts`.

```
available = max(0, takeHomeMonthly − expenseMonthly)   // monthly surplus
free      = round(available × 0.5)                    // FREE_BUDGET_SHARE
premMth   = (sum of included protection annual premiums) / 12
contribMth = sum of included wealth monthly contributions
monthly   = premMth + contribMth
monthlyOver = monthly − free
lumpOver    = wealth lumps − liquid savings
```

So the “budget” the customer sees is **half of monthly surplus**, compared with plan premiums plus savings contributions. It is not FM’s Need Calculator.
