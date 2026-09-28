import {
  NEED_META,
  POLICY_FOR_NEED,
  MAX_RETIREMENT_AGE,
  availableBudget,
  sessionAge,
  type GpSession,
  type NeedRow,
  type NeedType,
} from './types';

export const MANDATORY_NEEDS: NeedType[] = ['N_RET'];
export const SCORE_NEED_CAP = 4;
const GROUP_N = 2;

function byNeedWeight(a: NeedRow, b: NeedRow): number {
  return (b.gap || 0) - (a.gap || 0) || (b.needAmount || 0) - (a.needAmount || 0);
}

export function capEnabledNeeds(needs: NeedRow[]): NeedRow[] {
  const withMand = needs.map(n => (n.type === 'N_RET' ? { ...n, enabled: true } : n));
  const pick = (group: 'p' | 'w', must: NeedType[]) => {
    const pool = withMand.filter(n => NEED_META[n.type].group === group).sort(byNeedWeight);
    const keep: NeedType[] = [...must];
    const enabled = pool.filter(n => n.enabled && !must.includes(n.type));
    const rest = pool.filter(n => !n.enabled && !must.includes(n.type));
    for (const n of [...enabled, ...rest]) {
      if (keep.length >= GROUP_N) break;
      keep.push(n.type);
    }
    return keep.slice(0, GROUP_N);
  };
  const keep = new Set<NeedType>([...pick('p', []), ...pick('w', ['N_RET'])]);
  return withMand.map(n => ({ ...n, enabled: keep.has(n.type) }));
}

/** User toggle: any catalog goal can be on together. Retirement stays on. */
export function toggleNeedEnabled(needs: NeedRow[], type: NeedType): NeedRow[] {
  return needs.map(n => {
    if (n.type === 'N_RET') return { ...n, enabled: true };
    if (n.type === type) return { ...n, enabled: !n.enabled };
    return n;
  });
}

/** Retirement lifestyle rates. Mirror goal_math.RET_LIFESTYLE_FRUGAL / _STRESSFREE / _ONLYTHEBEST. */
export const LIFESTYLE: { v: number; label: string; rate: number }[] = [
  { v: 1, label: 'Frugal', rate: 0.75 },
  { v: 2, label: 'Stress free', rate: 1 },
  { v: 3, label: 'Only the best', rate: 1.25 },
];

export interface NeedEdit {
  retAge: number;
  lifestyle: number;
  retIncomeMonthly: number;
  incomeReplaceMonthly: number;
  dependYears: number;
  dependants: number;
  liabilities: number;
  bequest: number;
  existing: number;
  targetYear: number;
  amountRequired: number;
  monthlyContribution: number;
  contributeYears: number;
  ltcStartAge: number;
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

/** Years of income support behind the income need. Mirrors goal_math.income_support_years. */
export function incomeSupportYears(age: number): number {
  return Math.min(Math.max(10, 50 - (age || 0)), 25);
}

/** Read stored editor fields. Amounts / have / gap come from POST /v1/needs. */
export function fillNeedEdit(s: GpSession, n: NeedRow): NeedEdit {
  const rawRet = n.retAge || s.ageOfRetirement || 65;
  const retAge = Math.min(MAX_RETIREMENT_AGE, Math.max(sessionAge(s) || 18, rawRet));
  const lifestyle = n.lifestyle === 1 || n.lifestyle === 3 ? n.lifestyle : 2;
  const y = nowYear();
  const targetYear = n.targetYear || n.fundsNeededYear || s.goalTargetYears?.[n.type] || y + 10;
  const yearsTo = Math.max(1, targetYear - y);
  const stored = n.existing ?? n.existingInvestment ?? n.existingSumAssured ?? 0;
  const surplus = Math.max(0, availableBudget(s));
  const inc = s.incomeMonthly || 0;
  const existingCap =
    NEED_META[n.type].group === 'p'
      ? moneyMax(n.needAmount || 0, 500000)
      : investmentRoom(s, n.type);
  return {
    retAge,
    lifestyle,
    retIncomeMonthly: n.retIncomeMonthly ?? 0,
    incomeReplaceMonthly: Math.min(n.incomeReplaceMonthly ?? inc, moneyMax(inc, 20000)),
    dependYears: n.dependYears ?? incomeSupportYears(sessionAge(s) ?? 40),
    dependants: Math.min(6, n.dependants ?? s.dependents ?? 0),
    liabilities: Math.min(n.liabilities ?? s.mortgage ?? 0, moneyMax(s.mortgage || 0, 200000)),
    bequest: Math.max(0, n.bequest ?? 0),
    existing: Math.min(Number(stored) || 0, existingCap),
    targetYear,
    amountRequired:
      n.type === 'N_SAV' || n.type === 'N_PRP'
        ? Math.min(n.needAmount || 0, moneyMax(0, 5_000_000))
        : n.needAmount || 0,
    monthlyContribution: Math.min(n.monthlyContribution ?? 0, moneyMax(Math.max(surplus, 2000), 5000)),
    contributeYears: n.contributeYears ?? yearsTo,
    ltcStartAge: n.ltcStartAge ?? s.ltcStartAge ?? 80,
  };
}

export function needCardHave(_s: GpSession, n: NeedRow): number {
  return Math.round(n.have ?? 0);
}

export function needCardGap(_s: GpSession, n: NeedRow): number {
  if (n.gap != null) return Math.max(0, n.gap);
  return Math.max(0, (n.needAmount || 0) - (n.have || 0));
}

export function needsProvenanceYou(s: GpSession): GpSession['provenance'] {
  return { ...s.provenance, needs: 'you' };
}

/** Write slider inputs onto the need row. Does not compute amount / have / gap. */
export function patchNeedInputs(
  s: GpSession,
  type: NeedType,
  p: Partial<NeedRow>,
): Partial<GpSession> {
  const n = s.needs.find(x => x.type === type);
  if (!n) return {};
  const next: NeedRow = { ...n, ...p };
  if (p.targetYear != null) next.fundsNeededYear = p.targetYear;
  if (p.existing != null) {
    if (NEED_META[type].group === 'p') next.existingSumAssured = p.existing;
    else next.existingInvestment = p.existing;
  }
  const extra: Partial<GpSession> = {
    needs: s.needs.map(x => (x.type === type ? next : x)),
  };
  if (type === 'N_RET' && next.retAge) {
    next.retAge = Math.min(MAX_RETIREMENT_AGE, next.retAge);
    extra.ageOfRetirement = next.retAge;
    extra.needs = s.needs.map(x => (x.type === type ? next : x));
  }

  const want = POLICY_FOR_NEED[type];
  if (want && p.existing != null) {
    const rest = s.policies.filter(x => x.type !== want);
    const prev = s.policies.find(x => x.type === want);
    extra.policies =
      p.existing > 0
        ? [{ type: want, insurer: prev?.insurer || 'Existing insurer', sum: p.existing, premium: prev?.premium || 0 }, ...rest]
        : rest;
  }
  if (Object.keys(p).length) extra.provenance = needsProvenanceYou(s);
  return extra;
}

/** Dollar slider ceiling. Stops a drag-to-end from raising max again (value × 1.6 feedback). */
export const MONEY_SLIDER_CAP = 10_000_000;

/** Spend floor in system currency (USD). Convert with ``minExpenseMonthly``. */
export const MIN_EXPENSE_MONTHLY_USD = 100;

/** USD 100 as a monthly spend floor in the session's locked currency (2 dp, same as PLU). */
export function minExpenseMonthly(session?: { fx?: { usdPerLocal?: number } | null } | null): number {
  const rate = session?.fx?.usdPerLocal;
  if (rate == null || !(rate > 0)) return MIN_EXPENSE_MONTHLY_USD;
  return Math.round((MIN_EXPENSE_MONTHLY_USD / rate) * 100) / 100;
}

const WEALTH_TAG_ORDER: NeedType[] = ['N_RET', 'N_EDU', 'N_SAV', 'N_PRP'];

/** Investments still free for this need. Earlier wealth tags consume the pot first. Cash is not in the pot. */
export function investmentRoom(s: GpSession, type: NeedType): number {
  const pot = s.investments || 0;
  let used = 0;
  for (const t of WEALTH_TAG_ORDER) {
    if (t === type) break;
    const row = s.needs.find(n => n.type === t);
    used += row?.existing ?? row?.existingInvestment ?? 0;
  }
  return Math.max(0, pot - used);
}

export function moneyMax(base: number, floor: number): number {
  const stretched = Math.ceil((Math.max(base, 0) * 1.6) / 1000) * 1000;
  return Math.min(MONEY_SLIDER_CAP, Math.max(floor, stretched));
}

/** Singapore-reasonable floors for Money-page figure sliders. Max is moneyMax(value at open, floor). */
export const MONEY_FIELD_SLIDER: Record<string, { floor: number; step: number; perMonth?: boolean }> = {
  income: { floor: 20_000, step: 100, perMonth: true },
  expense: { floor: 15_000, step: 100, perMonth: true },
  savings: { floor: 200_000, step: 5_000 },
  cash: { floor: 200_000, step: 5_000 },
  investments: { floor: 500_000, step: 10_000 },
  property: { floor: 2_000_000, step: 50_000 },
  loans: { floor: 1_000_000, step: 25_000 },
};

export const MONEY_EDIT_TIP: Record<string, string> = {
  income: 'einc',
  expense: 'eexp',
  cash: 'esav',
  investments: 'einv',
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
