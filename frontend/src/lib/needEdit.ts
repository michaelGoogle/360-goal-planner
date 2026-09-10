import {
  NEED_META,
  availableBudget,
  needHave,
  sessionAge,
  type GpSession,
  type NeedRow,
  type NeedType,
} from './types';

export const LIFESTYLE: { v: number; label: string; rate: number }[] = [
  { v: 1, label: 'Frugal', rate: 0.5 },
  { v: 2, label: 'Stress free', rate: 0.67 },
  { v: 3, label: 'Only the best', rate: 1 },
];

export const EDU_REGIONS: { k: string; label: string; yearCost: number }[] = [
  { k: 'R_SGP', label: 'Singapore', yearCost: 18000 },
  { k: 'R_AUS', label: 'Australia', yearCost: 12270 },
  { k: 'R_UK', label: 'UK', yearCost: 32000 },
  { k: 'R_CAN', label: 'Canada', yearCost: 22000 },
  { k: 'R_USA', label: 'USA', yearCost: 48000 },
];

const POLICY_FOR: Partial<Record<NeedType, string>> = {
  N_INC: 'Life Protection',
  N_CRI: 'Critical Illness',
  N_TPD: 'Permanent Disability',
};

export interface NeedEdit {
  retAge: number;
  lifestyle: number;
  retIncomeMonthly: number;
  incomeReplaceMonthly: number;
  dependYears: number;
  dependants: number;
  liabilities: number;
  existing: number;
  targetYear: number;
  amountRequired: number;
  monthlyContribution: number;
  contributeYears: number;
  region: string;
  courseYears: number;
  childrenToFund: number;
}

function roundTo(n: number, step: number): number {
  return Math.max(0, Math.round(n / step) * step);
}

function pvAnnuity(pmt: number, rate: number, periods: number): number {
  if (periods <= 0 || pmt <= 0) return 0;
  if (Math.abs(rate) < 1e-12) return pmt * periods;
  return (pmt * (1 - Math.pow(1 + rate, -periods))) / rate;
}

export function fv(pv: number, rate: number, periods: number): number {
  if (periods <= 0) return Math.max(0, pv);
  return pv * Math.pow(1 + rate, periods);
}

export function fvAnnuity(pmt: number, rate: number, periods: number): number {
  if (periods <= 0 || pmt <= 0) return 0;
  if (Math.abs(rate) < 1e-12) return pmt * periods;
  return (pmt * (Math.pow(1 + rate, periods) - 1)) / rate;
}

export function realReturn(s: GpSession): number {
  const nom = s.investmentReturn || 0.042;
  const inf = s.inflationRate || 0.023;
  return Math.max(0, (1 + nom) / (1 + inf) - 1);
}

export function nowYear(): number {
  return new Date().getFullYear();
}

export function fillNeedEdit(s: GpSession, n: NeedRow): NeedEdit {
  const retAge = n.retAge || s.ageOfRetirement || 65;
  const lifestyle = n.lifestyle === 1 || n.lifestyle === 3 ? n.lifestyle : 2;
  const rate = LIFESTYLE.find(x => x.v === lifestyle)?.rate ?? 0.67;
  const y = nowYear();
  const targetYear = n.targetYear || n.fundsNeededYear || y + 10;
  const yearsTo = Math.max(1, targetYear - y);
  const stored = n.existing ?? n.existingInvestment ?? n.existingSumAssured ?? null;
  const existingRaw =
    stored != null && Number(stored) > 0
      ? Number(stored)
      : n.type === 'N_RET' || NEED_META[n.type].group === 'p'
        ? needHave(s, n)
        : 0;
  const surplus = Math.max(0, availableBudget(s));
  const inc = s.incomeMonthly || 0;
  const liq = (s.cash || 0) + (s.investments || 0);
  const existingCap =
    NEED_META[n.type].group === 'p'
      ? moneyMax(n.needAmount || 0, 500000)
      : moneyMax(liq, n.type === 'N_RET' ? 500000 : 200000);
  return {
    retAge,
    lifestyle,
    retIncomeMonthly: n.retIncomeMonthly ?? roundTo(inc * rate, 50),
    incomeReplaceMonthly: Math.min(n.incomeReplaceMonthly ?? inc, moneyMax(inc, 20000)),
    dependYears: n.dependYears ?? (s.dependents > 0 ? 20 : 10),
    dependants: Math.min(6, n.dependants ?? s.dependents ?? 0),
    liabilities: Math.min(n.liabilities ?? s.mortgage ?? 0, moneyMax(s.mortgage || 0, 200000)),
    existing: Math.min(existingRaw, existingCap),
    targetYear,
    amountRequired:
      n.type === 'N_SAV' || n.type === 'N_PRP'
        ? Math.min(n.needAmount || 0, moneyMax(0, 5_000_000))
        : n.needAmount || 0,
    monthlyContribution: Math.min(n.monthlyContribution ?? 0, moneyMax(Math.max(surplus, 2000), 5000)),
    contributeYears: n.contributeYears ?? yearsTo,
    region: n.region || (n.type === 'N_EDU' ? 'R_AUS' : 'R_SGP'),
    courseYears: n.courseYears ?? 4,
    childrenToFund: n.childrenToFund ?? Math.max(1, s.dependents || 1),
  };
}

export function computeNeedAmount(s: GpSession, n: NeedRow, e = fillNeedEdit(s, n)): number {
  const age = sessionAge(s) || 40;
  const inf = s.inflationRate || 0.023;
  if (n.type === 'N_RET') {
    const yrs = Math.max(0, e.retAge - age);
    const annual = e.retIncomeMonthly * 12;
    const atRet = annual * Math.pow(1 + inf, yrs);
    return Math.round(pvAnnuity(atRet, inf, 20));
  }
  if (n.type === 'N_INC' || n.type === 'N_TPD') {
    return Math.round(e.incomeReplaceMonthly * 12 * e.dependYears + e.liabilities);
  }
  if (n.type === 'N_CRI') {
    return Math.round(e.incomeReplaceMonthly * 12 * 5);
  }
  if (n.type === 'N_EDU') {
    const cost = EDU_REGIONS.find(x => x.k === e.region)?.yearCost ?? 18000;
    return Math.round(cost * e.courseYears * e.childrenToFund);
  }
  return Math.round(e.amountRequired || n.needAmount || 0);
}

export function needProjected(s: GpSession, n: NeedRow, e = fillNeedEdit(s, n)): number {
  const r = realReturn(s);
  const age = sessionAge(s) || 40;
  if (NEED_META[n.type].group !== 'w') return Math.round(e.existing);
  if (n.type === 'N_RET') return Math.round(fv(e.existing, r, Math.max(0, e.retAge - age)));
  const yrs = Math.max(0, e.targetYear - nowYear());
  const grown = fv(e.existing, r, yrs);
  if (n.type === 'N_EDU') return Math.round(grown);
  return Math.round(grown + fvAnnuity(e.monthlyContribution * 12, r, e.contributeYears));
}

export function needCardHave(s: GpSession, n: NeedRow): number {
  return NEED_META[n.type].group === 'w' ? needProjected(s, n) : needHave(s, n);
}

export function needCardGap(s: GpSession, n: NeedRow): number {
  return Math.max(0, (n.needAmount || 0) - needCardHave(s, n));
}

export function applyNeedPatch(
  s: GpSession,
  type: NeedType,
  p: Partial<NeedRow>,
): { needs: NeedRow[]; extra: Partial<GpSession> } {
  const n = s.needs.find(x => x.type === type);
  if (!n) return { needs: s.needs, extra: {} };
  const next: NeedRow = { ...n, ...p };
  if (p.lifestyle != null && p.retIncomeMonthly == null) {
    const rate = LIFESTYLE.find(x => x.v === p.lifestyle)?.rate ?? 0.67;
    next.retIncomeMonthly = roundTo((s.incomeMonthly || 0) * rate, 50);
  }
  const filled = fillNeedEdit(s, next);
  next.needAmount = computeNeedAmount(s, next, filled);
  next.retAge = filled.retAge;
  next.lifestyle = filled.lifestyle;
  next.retIncomeMonthly = filled.retIncomeMonthly;
  next.incomeReplaceMonthly = filled.incomeReplaceMonthly;
  next.dependYears = filled.dependYears;
  next.dependants = filled.dependants;
  next.liabilities = filled.liabilities;
  next.targetYear = filled.targetYear;
  next.fundsNeededYear = filled.targetYear;
  next.monthlyContribution = filled.monthlyContribution;
  next.contributeYears = filled.contributeYears;
  next.region = filled.region;
  next.courseYears = filled.courseYears;
  next.childrenToFund = filled.childrenToFund;
  next.existing = p.existing != null ? p.existing : filled.existing;
  if (NEED_META[type].group === 'p') next.existingSumAssured = next.existing;
  else next.existingInvestment = next.existing;

  const extra: Partial<GpSession> = {};
  if (type === 'N_RET') extra.ageOfRetirement = next.retAge;

  const want = POLICY_FOR[type];
  if (want && p.existing != null) {
    const rest = s.policies.filter(x => x.type !== want);
    const prev = s.policies.find(x => x.type === want);
    extra.policies =
      p.existing > 0
        ? [{ type: want, insurer: prev?.insurer || 'Existing insurer', sum: p.existing, premium: prev?.premium || 0 }, ...rest]
        : rest;
  }

  return {
    needs: s.needs.map(x => (x.type === type ? next : x)),
    extra,
  };
}

/** Dollar slider ceiling. Stops a drag-to-end from raising max again (value × 1.6 feedback). */
export const MONEY_SLIDER_CAP = 10_000_000;

export function moneyMax(base: number, floor: number): number {
  const stretched = Math.ceil((Math.max(base, 0) * 1.6) / 1000) * 1000;
  return Math.min(MONEY_SLIDER_CAP, Math.max(floor, stretched));
}

/** Singapore-reasonable floors for Money-page figure sliders. Max is moneyMax(value at open, floor). */
export const MONEY_FIELD_SLIDER: Record<string, { floor: number; step: number; perMonth?: boolean }> = {
  income: { floor: 20_000, step: 100, perMonth: true },
  expense: { floor: 15_000, step: 100, perMonth: true },
  savings: { floor: 500_000, step: 10_000 },
  property: { floor: 2_000_000, step: 50_000 },
  loans: { floor: 1_000_000, step: 25_000 },
};

export const MONEY_EDIT_TIP: Record<string, string> = {
  income: 'einc',
  expense: 'eexp',
  savings: 'esav',
  property: 'eprp',
  loans: 'eloan',
};

export const COVER_FIELD_SLIDER = {
  sum: { floor: 2_000_000, step: 10_000 },
  premium: { floor: 12_000, step: 10 },
};

export function yearsWord(n: number): string {
  return `${n} year${n === 1 ? '' : 's'}`;
}

export function surplusAnnual(s: GpSession): number {
  return Math.max(0, availableBudget(s) * 12);
}
