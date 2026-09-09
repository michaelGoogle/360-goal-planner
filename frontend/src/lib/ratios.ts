export interface Ratio {
  k: string;
  n: string;
  v: number;
  unit: string;
  ok: boolean;
  rec: string;
  good: string;
  bad: string;
}

export function moneyRatios(opts: {
  income: number;
  expense: number;
  cash: number;
  investments: number;
  property: number;
  mortgage: number;
}): Ratio[] {
  const { income, expense, cash, investments, property, mortgage } = opts;
  const assets = cash + investments + property;
  const nw = assets - mortgage;
  const sav = income - expense;
  const loanPayM = mortgage > 0 ? mortgage / 240 : 0;
  const d = (a: number, b: number) => (b ? a / b : 0);
  return [
    {
      k: 'liq',
      n: 'Basic Liquidity Ratio',
      v: d(cash, expense),
      unit: 'months',
      rec: '3 to 6 months',
      ok: d(cash, expense) >= 3,
      good: 'You are financially prepared should you face an unexpected expense or lost income.',
      bad: 'You may not be prepared for an unexpected expense or a loss of income.',
    },
    {
      k: 'lnw',
      n: 'Liquid assets to net worth ratio',
      v: d(cash, nw) * 100,
      unit: '%',
      rec: 'at least 15%',
      ok: d(cash, nw) * 100 >= 15,
      good: 'You have a healthy balance of cash and assets.',
      bad: 'Consider holding more of your net worth in cash so it is there when you need it.',
    },
    {
      k: 'dsr',
      n: 'Debt service ratio',
      v: d(loanPayM, income) * 100,
      unit: '%',
      rec: '35% or less',
      ok: d(loanPayM, income) * 100 <= 35,
      good: 'You are able to pay off your loans comfortably.',
      bad: 'A large share of your income is going to debt repayment.',
    },
    {
      k: 'dar',
      n: 'Debt asset ratio',
      v: d(mortgage, assets) * 100,
      unit: '%',
      rec: '50% or less',
      ok: d(mortgage, assets) * 100 <= 50,
      good: 'You own most of your assets.',
      bad: 'A large share of your assets is financed by borrowing.',
    },
    {
      k: 'sav',
      n: 'Savings ratio',
      v: d(sav, income) * 100,
      unit: '%',
      rec: '10% - 20%',
      ok: d(sav, income) * 100 >= 10,
      good: 'You are saving a healthy proportion of your income.',
      bad: 'Consider setting aside more of your income each month.',
    },
    {
      k: 'inw',
      n: 'Total investment assets to net worth ratio',
      v: d(investments, nw) * 100,
      unit: '%',
      rec: 'at least 50%',
      ok: d(investments, nw) * 100 >= 50,
      good: 'Your wealth is working for you across a range of invested assets.',
      bad: 'Consider investing more to help grow your wealth over time.',
    },
  ];
}

export function rnum(v: number): string {
  return Number(v || 0).toFixed(2);
}
