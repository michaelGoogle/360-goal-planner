import { ASSUME_DEFAULTS, pctAn, type AssumeKey } from '../../lib/assumptions';
import { needCardGap, needCardHave } from '../../lib/needEdit';
import {
  PLAN_FOR_NEED,
  planAfford,
  planCoverPrem,
  planCoverSum,
  planIncluded,
  planLump,
  planMonthly,
  planRemain,
  suggestedNeeds,
} from '../../lib/planProducts';
import { moneyRatios, rnum } from '../../lib/ratios';
import { pickAvailable, type SvData } from '../../lib/sv';
import {
  NEED_META,
  coverSum,
  firstName,
  happiCaption,
  liquid,
  money,
  netWealth,
  sessionAge,
  type GpSession,
  type NeedRow,
  type Prov,
} from '../../lib/types';

export interface WalkSlide {
  kicker: string;
  title: string;
  lines: { label: string; value: string }[];
}

export function reportPrintedOn(): string {
  return new Date().toLocaleDateString('en-SG', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function provLabel(p: Prov | undefined): string {
  if (p === 'doc') return 'From your documents';
  if (p === 'you') return 'Your own figures';
  return 'People Like You estimate';
}

export function goalRows(session: GpSession) {
  return [...session.needs]
    .map(n => ({
      ...n,
      have: needCardHave(session, n),
      gap: needCardGap(session, n),
    }))
    .sort((a, b) => Number(b.enabled) - Number(a.enabled) || (b.gap || 0) - (a.gap || 0));
}

export function biggestGap(session: GpSession): NeedRow | null {
  const on = session.needs.filter(n => n.enabled);
  if (!on.length) return null;
  return [...on].sort((a, b) => needCardGap(session, b) - needCardGap(session, a))[0] ?? null;
}

export function ratioSummary(session: GpSession) {
  const rows = moneyRatios({
    income: session.incomeMonthly,
    expense: session.expenseMonthly,
    cash: session.cash,
    investments: session.investments,
    property: session.property,
    mortgage: session.mortgage,
  });
  return { rows, ok: rows.filter(r => r.ok).length };
}

export function outlookEnds(svData: SvData | null) {
  if (!svData) return { without: null as number | null, withPlan: null as number | null };
  const pre = pickAvailable(svData, 'pre');
  const post = pickAvailable(svData, 'post');
  return {
    without: pre.length ? pre[pre.length - 1]! : null,
    withPlan: post.length ? post[post.length - 1]! : null,
  };
}

export function changedAssumptions(session: GpSession) {
  return (Object.keys(ASSUME_DEFAULTS) as AssumeKey[])
    .filter(k => Math.round(session[k] * 1000) !== Math.round(ASSUME_DEFAULTS[k] * 1000))
    .map(k => ({
      key: k,
      value: pctAn(session[k]),
      base: pctAn(ASSUME_DEFAULTS[k]),
    }));
}

const ASSUME_LABEL: Record<AssumeKey, string> = {
  inflationRate: 'Inflation',
  interestRate: 'Cash interest',
  incomeGrowthRate: 'Income growth',
  investmentReturn: 'Investment return',
  assetReturn: 'Asset return',
};

export function assumeLabel(k: AssumeKey): string {
  return ASSUME_LABEL[k];
}

export function walkSlides(
  session: GpSession,
  pre: number | null,
  post: number | null,
  svData: SvData | null,
): WalkSlide[] {
  const name = firstName(session);
  const age = sessionAge(session);
  const score = post ?? pre ?? 0;
  const gap = biggestGap(session);
  const ratios = ratioSummary(session);
  const afford = planAfford(session);
  const ends = outlookEnds(svData);
  const who = name === 'you' ? 'You' : name;
  return [
    {
      kicker: 'Your plan',
      title: `${who}’s snapshot`,
      lines: [
        { label: 'Age', value: age ? String(age) : '—' },
        { label: 'HappiU today', value: pre == null ? '—' : String(Math.round(pre)) },
        { label: 'HappiU with this plan', value: post == null ? '—' : String(Math.round(post)) },
        { label: 'Band', value: happiCaption(score).split(':')[0] || '—' },
      ],
    },
    {
      kicker: 'About you',
      title: session.occupation || 'Your profile',
      lines: [
        { label: 'Residency', value: session.residency || '—' },
        { label: 'Dependants', value: String(session.dependents ?? 0) },
        { label: 'Retire at', value: String(session.ageOfRetirement || 65) },
      ],
    },
    {
      kicker: 'Your money',
      title: 'What you hold today',
      lines: [
        { label: 'Income / month', value: money(session.incomeMonthly) },
        { label: 'Spend / month', value: money(session.expenseMonthly) },
        { label: 'Liquid savings', value: money(liquid(session)) },
        { label: 'Net wealth', value: money(netWealth(session)) },
      ],
    },
    {
      kicker: 'Your goals',
      title: gap ? NEED_META[gap.type].label : 'Goals in this plan',
      lines: gap
        ? [
            { label: 'Need', value: money(gap.needAmount || 0) },
            { label: 'Have', value: money(needCardHave(session, gap)) },
            { label: 'Largest gap', value: money(needCardGap(session, gap)) },
          ]
        : [{ label: 'Activated goals', value: String(session.needs.filter(n => n.enabled).length) }],
    },
    {
      kicker: 'Your score',
      title: happiCaption(score).split(':')[0] || 'HappiU',
      lines: [
        { label: 'Money-health ratios in good shape', value: `${ratios.ok} of ${ratios.rows.length}` },
        { label: 'Existing cover', value: money(coverSum(session)) },
      ],
    },
    {
      kicker: 'Your plan',
      title: afford.monthlyOver > 0 ? 'Over free budget' : 'Fits the free budget',
      lines: [
        { label: 'Premiums & contributions', value: `${money(afford.monthly)} / mo` },
        { label: 'Recommended free budget', value: money(afford.free) },
        {
          label: `Wealth at age ${session.endAge || 85}`,
          value:
            ends.withPlan == null
              ? 'Chart not ready'
              : `${money(ends.without ?? 0)} → ${money(ends.withPlan)}`,
        },
      ],
    },
  ];
}

export function planLines(session: GpSession) {
  return suggestedNeeds(session).map(n => {
    const protect = NEED_META[n.type].group === 'p';
    return {
      type: n.type,
      title: PLAN_FOR_NEED[n.type],
      on: planIncluded(session, n.type),
      remain: planRemain(session, n.type),
      detail: protect
        ? `${money(planCoverSum(session, n.type))} cover · ${money(planCoverPrem(session, n.type))} / yr`
        : `${money(planLump(session, n.type))} lump · ${money(planMonthly(session, n.type))} / mo`,
    };
  });
}

export { moneyRatios, rnum };
