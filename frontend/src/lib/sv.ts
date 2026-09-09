export type ChartView = 'wealth' | 'cash' | 'exp' | 'sav';

export interface ExpenseFunding {
  active: number[];
  passive: number[];
  savings: number[];
  shortfall: number[];
}

/** Scenario Visualizer `data` envelope — the series the Plan chart plots. */
export interface SvData {
  preWealth: number[];
  preAvailableWealth?: number[] | null;
  preEarmarkedWealth?: number[] | null;
  prePositiveCashFlow: number[];
  preNegativeCashFlow: number[];
  preExpenseFunding?: ExpenseFunding | null;
  postWealth: number[];
  postAvailableWealth?: number[] | null;
  postEarmarkedWealth?: number[] | null;
  postPositiveCashFlow: number[];
  postNegativeCashFlow: number[];
  postExpenseFunding?: ExpenseFunding | null;
}

export function isSvData(v: unknown): v is SvData {
  if (!v || typeof v !== 'object') return false;
  const d = v as SvData;
  return Array.isArray(d.preWealth);
}

function floor(series: number[] | null | undefined): number[] {
  return (series || []).map(v => Math.max(0, Number(v) || 0));
}

function hasSignal(series: number[] | null | undefined): boolean {
  return !!series?.some(v => Math.abs(Number(v) || 0) > 0.5);
}

export function pickAvailable(data: SvData, side: 'pre' | 'post'): number[] {
  const avail = side === 'pre' ? data.preAvailableWealth : data.postAvailableWealth;
  const total = side === 'pre' ? data.preWealth : data.postWealth;
  if (avail?.length) return floor(avail);
  return floor(total);
}

export function pickEarmarked(data: SvData, side: 'pre' | 'post'): number[] | null {
  const raw = side === 'pre' ? data.preEarmarkedWealth : data.postEarmarkedWealth;
  return hasSignal(raw) ? floor(raw) : null;
}

export function pickFunding(data: SvData): ExpenseFunding | null {
  const raw = data.preExpenseFunding?.active?.length ? data.preExpenseFunding : data.postExpenseFunding;
  if (!raw?.active?.length) return null;
  return raw;
}

export function seriesLength(data: SvData): number {
  return Math.max(
    data.preWealth?.length || 0,
    data.postWealth?.length || 0,
    data.prePositiveCashFlow?.length || 0,
    data.postPositiveCashFlow?.length || 0,
    data.preExpenseFunding?.active?.length || 0,
  );
}

export const SV_COLORS = {
  wealth: '#5B8DEF',
  wealthFill: 'rgba(91, 141, 239, 0.28)',
  earmarked: '#26A69A',
  earmarkedFill: 'rgba(38, 166, 154, 0.22)',
  inflow: '#81C784',
  outflow: '#EF735C',
  active: '#4A6CF7',
  passive: '#9C27B0',
  savings: '#80CBC4',
  shortfall: '#EF5350',
} as const;

/** Chart title + (i) copy — same wording as Scenario Visualizer. */
export function chartCopy(view: ChartView, earmarked: boolean): { title: string; info: string } {
  if (view === 'cash') {
    return {
      title: 'Cash inflow & outflow',
      info: 'Year-by-year money in (income, payouts, maturities) versus money out (living costs, premiums, goal spends). Policy pots: contribution is cash out, pot earns 3%, maturity is cash in. Fund from own assets: set-asides stay inside wealth (not shown as cash out) and earn 3%; savings spends and property purchases still appear when money is used.',
    };
  }
  if (view === 'exp') {
    return {
      title: 'How expenses are funded',
      info: 'For each year, how expenses are covered: active income, passive income, draws from available savings, or unmet shortfall. Pots set aside under “fund from my assets” are reserved for goals and do not count as available savings here.',
    };
  }
  if (earmarked) {
    return {
      title: 'Available & earmarked assets',
      info: 'Available assets exclude pots set aside under “fund from my assets”. The earmarked line is those goal pots while they accumulate (at ~3%); at the goal year the pot liquidates into available cash (savings spend, property purchase, or retirement funding) and earmarked drops. Gross of liabilities.',
    };
  }
  return {
    title: 'Projected assets',
    info: 'Stock of assets over time: investments, property, cash/savings buffer, CPF, and accumulation pots. Gross assets — liabilities are not subtracted.',
  };
}
