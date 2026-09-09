import { moneyRatios } from './ratios';
import { pickAvailable, type ChartView, type SvData } from './sv';
import {
  availableBudget,
  employeeCpfMonthly,
  NEED_META,
  d2cReady,
  firstName,
  happiBand,
  liquid,
  needGap,
  needHave,
  netWealth,
  sessionAge,
  type GpSession,
  type Route,
} from './types';

export type ExplainKind = 'mira' | 'intro' | 'money' | 'score' | 'chart' | 'prod';

export interface ExplainResponse {
  success: boolean;
  kind: string;
  source: string;
  text: string;
}

function seriesStats(arr: number[] | null | undefined) {
  if (!arr?.length) return null;
  const nums = arr.map(v => Number(v) || 0);
  return { first: nums[0], last: nums[nums.length - 1], min: Math.min(...nums), max: Math.max(...nums) };
}

function missingLabels(s: GpSession): string[] {
  const read = s.sentenceRead || {};
  const T = s.touched;
  const req: [string, string][] = [
    ['name', 'name'],
    ['age', 'age'],
    ['gender', 'gender'],
    ['deps', 'dependants'],
    ['res', 'residency'],
    ['occ', 'occupation'],
  ];
  const val: Record<string, string> = {
    name: s.name,
    age: s.age === '' ? '' : String(s.age),
    gender: s.gender,
    deps: s.depsChoice,
    res: s.residency,
    nat: s.nationality,
    occ: s.occupation,
  };
  return req.filter(r => !read[r[0]] && !T[r[0]] && !(val[r[0]] || '').trim()).map(r => r[1]);
}

export function buildExplainContext(opts: {
  kind: ExplainKind;
  route: Route;
  session: GpSession;
  pre: number | null;
  post: number | null;
  svData: SvData | null;
  chartView?: ChartView;
}): Record<string, unknown> {
  const { session: s, pre, post, svData, chartView } = opts;
  const age = sessionAge(s);
  const mInc = s.incomeMonthly;
  const mExp = s.expenseMonthly;
  const R = moneyRatios({
    income: mInc,
    expense: mExp,
    cash: s.cash,
    investments: s.investments,
    property: s.property,
    mortgage: s.mortgage,
  });
  const withPlan = svData ? pickAvailable(svData, 'post') : [];
  const without = svData ? pickAvailable(svData, 'pre') : [];
  const withStats = seriesStats(withPlan);
  const withoutStats = seriesStats(without);

  return {
    kind: opts.kind,
    route: opts.route,
    you: {
      firstName: firstName(s),
      age,
      occupation: s.occupation || null,
      gender: s.gender,
      residency: s.residency,
      dependents: s.dependents,
      retirementAge: s.ageOfRetirement,
      ready: d2cReady(s),
    },
    missing: missingLabels(s),
    source: s.source || null,
    provenance: s.provenance,
    money: {
      incomeMonthly: mInc,
      expenseMonthly: mExp,
      cpfMonthly: employeeCpfMonthly(s),
      budgetMonthly: availableBudget(s),
      expenseSharePct: mInc ? Math.round((mExp / mInc) * 100) : null,
      cash: s.cash,
      investments: s.investments,
      liquid: liquid(s),
      property: s.property,
      mortgage: s.mortgage,
      netWealth: netWealth(s),
      coverSum: s.policies.reduce((t, p) => t + (p.sum || 0), 0),
      coverCount: s.policies.length,
    },
    needs: s.needs.map(n => ({
      type: n.type,
      label: NEED_META[n.type]?.label || n.type,
      enabled: n.enabled,
      need: n.needAmount,
      have: needHave(s, n),
      gap: needGap(s, n),
    })),
    score: {
      pre,
      post,
      band: pre == null ? null : happiBand(pre),
    },
    ratios: R.map(r => ({
      key: r.k,
      name: r.n,
      value: r.v,
      unit: r.unit,
      recommended: r.rec,
      ok: r.ok,
    })),
    chart: {
      view: chartView || 'wealth',
      startAge: age,
      endAge: s.endAge || 85,
      ready: !!svData && withPlan.length > 0,
      withPlanEnd: withStats?.last ?? null,
      withoutEnd: withoutStats?.last ?? null,
      lowest: withStats?.min ?? null,
    },
    products: {
      lifeOn: s.lifeOn,
      lifeSum: s.lifeSum,
      lifePrem: s.lifePrem,
      investOn: s.investOn,
      investMth: s.investMth,
      investLump: s.investLump,
    },
    events: s.events.map(e => ({ id: e.id, on: e.on, label: e.label })),
    assumptions: {
      inflationRate: s.inflationRate,
      interestRate: s.interestRate,
      incomeGrowthRate: s.incomeGrowthRate,
      investmentReturn: s.investmentReturn,
      assetReturn: s.assetReturn,
    },
  };
}
