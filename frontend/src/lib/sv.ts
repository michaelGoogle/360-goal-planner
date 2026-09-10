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

export function pickCashflow(data: SvData, side: 'pre' | 'post'): { inflow: number[]; outflow: number[] } {
  const inflow = side === 'post' ? data.postPositiveCashFlow : data.prePositiveCashFlow;
  const outflow = side === 'post' ? data.postNegativeCashFlow : data.preNegativeCashFlow;
  if (side === 'post' && !inflow?.length && !outflow?.length) {
    return { inflow: data.prePositiveCashFlow || [], outflow: data.preNegativeCashFlow || [] };
  }
  return { inflow: inflow || [], outflow: outflow || [] };
}

export function pickFunding(data: SvData, side: 'pre' | 'post' = 'pre'): ExpenseFunding | null {
  const raw = side === 'post' ? data.postExpenseFunding : data.preExpenseFunding;
  if (raw?.active?.length) return raw;
  const fallback = side === 'post' ? data.preExpenseFunding : data.postExpenseFunding;
  return fallback?.active?.length ? fallback : null;
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
  wealthWithout: '#C45C26',
  earmarked: '#26A69A',
  earmarkedFill: 'rgba(38, 166, 154, 0.22)',
  inflow: '#81C784',
  outflow: '#EF735C',
  active: '#4A6CF7',
  passive: '#9C27B0',
  savings: '#80CBC4',
  shortfall: '#EF5350',
} as const;

/** Chart title + (i) copy. `plansOn` is Apply this plan. */
export function chartCopy(view: ChartView, earmarked: boolean, plansOn = false): { title: string; info: string } {
  if (view === 'cash') {
    return {
      title: 'Cash inflow & outflow',
      info: plansOn
        ? 'With this plan: money in (income, payouts, maturities) versus money out (living costs, premiums, goal spends). Turn off Apply this plan to see cashflow without it.'
        : 'Without this plan: money in versus money out, with none of the recommended premiums or payouts. Turn on Apply this plan to include them.',
    };
  }
  if (view === 'exp') {
    return {
      title: 'How expenses are funded',
      info: plansOn
        ? 'With this plan: how each year\'s spending is covered — active income, passive income, draws from savings, or unmet shortfall. Turn off Apply this plan to see funding without it.'
        : 'Without this plan: how each year\'s spending is covered. Turn on Apply this plan to see whether the mix reduces the shortfall.',
    };
  }
  if (earmarked) {
    return {
      title: 'Available & earmarked assets',
      info: plansOn
        ? 'The solid line is this plan; the dotted line is without it. Available assets exclude pots set aside under “fund from my assets”. The earmarked line is those goal pots while they accumulate (at ~3%); at the goal year the pot liquidates into available cash and earmarked drops. Gross of liabilities.'
        : 'Available and earmarked assets without the recommended plan. Turn on Apply this plan to compare with versus without. Gross of liabilities.',
    };
  }
  return {
    title: 'Projected assets',
    info: plansOn
      ? 'The solid line is this plan; the dotted line is without it. Stock of assets over time: investments, property, cash/savings buffer, CPF, and accumulation pots. Gross assets — liabilities are not subtracted.'
      : 'Available assets without the recommended plan. Turn on Apply this plan to compare with versus without. Gross assets — liabilities are not subtracted.',
  };
}
