Kind: "Explain these figures" on the Your money screen.

Job: Read the balance-sheet card out loud, figure by figure, saying where each number came from before what it means.

Use `money`, `you`, `provenance`, and `source` from the JSON.

Cover, in order, one paragraph each:

1. Source of the estimates. If `source` is people-like-you or fallback, say these are estimates, not their records, worked out from occupation, age, and residency, using public salary references such as Glassdoor and local pay scales. If they have already overwritten figures (`provenance` values of `you` or `doc`), say so for those lines only.

2. Money coming in — `money.incomeMonthly` a month. Gross: before their own CPF contribution, including a twelfth of any bonus. If `source` is people-like-you, say this typical monthly income is informed by public sources like Glassdoor, not their payslip. If `provenance.income` is `doc`, it was read from a document. If `you`, they typed it.

3. Your CPF — `money.cpfMonthly` a month. Employee contribution only, not the employer’s. Citizens and PRs: 20% of ordinary wage to age 55, on wage up to S$8,000 (max S$1,600). Foreigners: zero. This line is calculated, not edited.

4. Money going out — `money.expenseMonthly` a month. A typical share of take-home (income less CPF): 67.5% with no dependants, plus 5 percentage points for each dependant, up to 90%. Covers everything including insurance premiums, but not CPF and not what they save. Tax is not deducted. If `provenance.expense` is `you`, they typed it. The donut folds CPF into money going out; this spoken line is spend only.

5. Available budget — income less CPF less spend (`money.budgetMonthly`). Cash left to save or put towards a goal. If negative, they are short each month.

6. What they own and owe, as balances: savings and investments (`money.liquid`), property (`money.property`), loans (`money.mortgage`), net wealth (`money.netWealth`).

7. Cover they already hold — `money.coverSum` of sum assured, or say they have no cover recorded. Every dollar of existing cover is subtracted from what they need, so cover they forget to add shows up as a bigger gap than they really have.

8. Close: if any figure is wrong, tap the pencil beside it. Everything after this screen follows from these numbers.
