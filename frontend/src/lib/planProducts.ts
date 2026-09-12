import { fillNeedEdit, fv, fvAnnuity, needCardGap, needCardHave, nowYear } from './needEdit';
import { NEED_META, NEED_TYPES, availableBudget, sessionAge, type GpSession, type NeedRow, type NeedType } from './types';

export const PLAN_FOR_NEED: Record<NeedType, string> = {
  N_INC: 'Life cover',
  N_CRI: 'Critical illness cover',
  N_TPD: 'Disability cover',
  N_RET: 'Retirement plan',
  N_SAV: 'Saving plan',
  N_EDU: 'Education plan',
  N_PRP: 'Property plan',
};

export function suggestedNeeds(session: GpSession): NeedRow[] {
  return session.needs
    .filter(n => n.enabled && needCardGap(session, n) > 0)
    .sort((a, b) => NEED_TYPES.indexOf(a.type) - NEED_TYPES.indexOf(b.type));
}

export function suggestedInGroup(session: GpSession, group: 'p' | 'w'): NeedRow[] {
  return suggestedNeeds(session).filter(n => NEED_META[n.type].group === group);
}

export function includedProtection(session: GpSession): NeedRow[] {
  return suggestedInGroup(session, 'p').filter(n => planIncluded(session, n.type));
}

export function protectionPremAnnual(session: GpSession): number {
  return includedProtection(session).reduce((sum, n) => sum + planCoverPrem(session, n.type), 0);
}

export function planIncluded(session: GpSession, type: NeedType): boolean {
  return !(session.plansOff || []).includes(type);
}

export function productFlags(session: GpSession): Pick<GpSession, 'lifeOn' | 'criOn' | 'tpdOn' | 'investOn'> {
  const on = suggestedNeeds(session).filter(n => planIncluded(session, n.type)).map(n => n.type);
  return {
    lifeOn: on.includes('N_INC'),
    criOn: on.includes('N_CRI'),
    tpdOn: on.includes('N_TPD'),
    investOn: on.some(t => NEED_META[t].group === 'w'),
  };
}

export function planMonthly(session: GpSession, type: NeedType): number {
  return session.planMth?.[type] ?? 0;
}

export function planLump(session: GpSession, type: NeedType): number {
  return session.planLump?.[type] ?? 0;
}

function includedWealth(session: GpSession) {
  return suggestedInGroup(session, 'w').filter(n => planIncluded(session, n.type));
}

export function investMthFromPlans(session: GpSession): number {
  return includedWealth(session).reduce((sum, n) => sum + planMonthly(session, n.type), 0);
}

export function investLumpFromPlans(session: GpSession): number {
  return includedWealth(session).reduce((sum, n) => sum + planLump(session, n.type), 0);
}

export function allPlansOn(session: GpSession): boolean {
  const rows = suggestedNeeds(session);
  return !!rows.length && rows.every(n => planIncluded(session, n.type));
}

export function anyPlanOn(session: GpSession): boolean {
  return suggestedNeeds(session).some(n => planIncluded(session, n.type));
}

export function toggleAllPlansPatch(session: GpSession): Partial<GpSession> {
  const rows = suggestedNeeds(session);
  const turnOn = !allPlansOn(session);
  const suggestedTypes = new Set(rows.map(n => n.type));
  const plansOff = turnOn
    ? (session.plansOff || []).filter(t => !suggestedTypes.has(t))
    : [...new Set([...(session.plansOff || []), ...rows.map(n => n.type)])];
  const next = { ...session, plansOff };
  return {
    plansOff,
    ...productFlags(next),
    investMth: investMthFromPlans(next),
    investLump: investLumpFromPlans(next),
  };
}

export function togglePlanPatch(session: GpSession, type: NeedType): Partial<GpSession> {
  const plansOff = planIncluded(session, type)
    ? [...new Set([...(session.plansOff || []), type])]
    : (session.plansOff || []).filter(t => t !== type);
  const next = { ...session, plansOff };
  return {
    plansOff,
    ...productFlags(next),
    investMth: investMthFromPlans(next),
    investLump: investLumpFromPlans(next),
  };
}

export function setPlanMthPatch(session: GpSession, type: NeedType, value: number): Partial<GpSession> {
  const planMth = { ...session.planMth, [type]: value };
  const next = { ...session, planMth };
  return { planMth, investMth: investMthFromPlans(next) };
}

export function setPlanLumpPatch(session: GpSession, type: NeedType, value: number): Partial<GpSession> {
  const planLumpNext = { ...session.planLump, [type]: value };
  const next = { ...session, planLump: planLumpNext };
  return { planLump: planLumpNext, investLump: investLumpFromPlans(next) };
}

export function planHorizonYears(session: GpSession, type: NeedType): number {
  const n = session.needs.find(x => x.type === type);
  if (!n) return 0;
  const e = fillNeedEdit(session, n);
  const age = sessionAge(session) || 40;
  if (type === 'N_RET') return Math.max(0, e.retAge - age);
  return Math.max(0, e.targetYear - nowYear());
}

export function planTargetYear(session: GpSession, type: NeedType): number {
  const n = session.needs.find(x => x.type === type);
  if (!n) return nowYear();
  const e = fillNeedEdit(session, n);
  if (type === 'N_RET') return nowYear() + planHorizonYears(session, type);
  return e.targetYear;
}

export function planRealRate(session: GpSession): number {
  const nom = session.investmentReturn || 0.042;
  const inf = session.inflationRate || 0.023;
  return Math.max(0, (1 + nom) / (1 + inf) - 1);
}

function roundUp(n: number, step: number): number {
  if (n <= 0) return 0;
  return Math.ceil(n / step) * step;
}

function pvToHitFv(target: number, rate: number, periods: number): number {
  if (target <= 0) return 0;
  if (periods <= 0) return target;
  if (Math.abs(rate) < 1e-12) return target;
  return target / Math.pow(1 + rate, periods);
}

function annualPmtToHitFv(target: number, rate: number, periods: number): number {
  if (target <= 0 || periods <= 0) return 0;
  if (Math.abs(rate) < 1e-12) return target / periods;
  return (target * rate) / (Math.pow(1 + rate, periods) - 1);
}

/** Lump (at $0 monthly) and monthly (at $0 lump) that close the remaining gap at the expected return. */
export function planSliderCaps(session: GpSession, type: NeedType): { lump: number; monthly: number } {
  const n = session.needs.find(x => x.type === type);
  const gap = n ? needCardGap(session, n) : 0;
  const yrs = planHorizonYears(session, type);
  const r = planRealRate(session);
  return {
    lump: roundUp(pvToHitFv(gap, r, yrs), 1000),
    monthly: roundUp(annualPmtToHitFv(gap, r, yrs) / 12, 50),
  };
}

export function clampPlanToCaps(session: GpSession, type: NeedType): Partial<GpSession> {
  const caps = planSliderCaps(session, type);
  const lump = Math.min(planLump(session, type), caps.lump);
  const mth = Math.min(planMonthly(session, type), caps.monthly);
  if (lump === planLump(session, type) && mth === planMonthly(session, type)) return {};
  const next = {
    ...session,
    planLump: { ...session.planLump, [type]: lump },
    planMth: { ...session.planMth, [type]: mth },
  };
  return {
    planLump: next.planLump,
    planMth: next.planMth,
    investLump: investLumpFromPlans(next),
    investMth: investMthFromPlans(next),
  };
}

export function clampAllWealthToCaps(session: GpSession): Partial<GpSession> {
  let next = session;
  const patch: Partial<GpSession> = {};
  for (const n of suggestedInGroup(session, 'w')) {
    const p = clampPlanToCaps(next, n.type);
    if (!Object.keys(p).length) continue;
    next = { ...next, ...p };
    Object.assign(patch, p);
  }
  return patch;
}

/** Future value of this plan's lump + monthly contributions, in today's money. */
export function planGrowthFvAt(session: GpSession, type: NeedType, lump: number, mth: number): number {
  const yrs = planHorizonYears(session, type);
  const r = planRealRate(session);
  return Math.round(fv(lump, r, yrs) + fvAnnuity(mth * 12, r, yrs));
}

export function planGrowthFv(session: GpSession, type: NeedType): number {
  return planGrowthFvAt(session, type, planLump(session, type), planMonthly(session, type));
}

/** Remaining gap after this suggested plan (negative if overfunded). */
export function planRemain(session: GpSession, type: NeedType): number {
  if (NEED_META[type].group === 'w') return planNeedFunding(session, type).remain;
  const n = session.needs.find(x => x.type === type);
  const gap = n ? needCardGap(session, n) : 0;
  if (!planIncluded(session, type)) return gap;
  return gap - planCoverSum(session, type);
}
export function planNeedFunding(
  session: GpSession,
  type: NeedType,
  lump = planLump(session, type),
  mth = planMonthly(session, type),
) {
  const n = session.needs.find(x => x.type === type);
  const have = n ? needCardHave(session, n) : 0;
  const req = n?.needAmount || 0;
  const extra = planIncluded(session, type) ? planGrowthFvAt(session, type, lump, mth) : 0;
  return { have, extra, req, covered: have + extra, remain: req - have - extra };
}

export function coverPremiumFor(sum: number): number {
  return Math.max(0, Math.round((sum * 0.00078) / 10) * 10);
}

export function coverSliderCaps(session: GpSession, type: NeedType): { sum: number; prem: number } {
  const n = session.needs.find(x => x.type === type);
  const gap = n ? needCardGap(session, n) : 0;
  const sum = Math.max(0, Math.round(gap));
  const indic = coverPremiumFor(sum);
  return { sum, prem: Math.max(indic * 2, 200) };
}

export function planCoverSum(session: GpSession, type: NeedType): number {
  if (session.planSum?.[type] != null) return session.planSum[type] ?? 0;
  return coverSliderCaps(session, type).sum;
}

export function planCoverPrem(session: GpSession, type: NeedType): number {
  if (session.planPrem?.[type] != null) return session.planPrem[type] ?? 0;
  const { prem } = coverSliderCaps(session, type);
  return Math.round(prem / 2 / 10) * 10;
}

export function setPlanCoverPatch(
  session: GpSession,
  type: NeedType,
  p: { sum?: number; prem?: number },
): Partial<GpSession> {
  const planSum = { ...session.planSum, [type]: p.sum ?? planCoverSum(session, type) };
  const planPrem = { ...session.planPrem, [type]: p.prem ?? planCoverPrem(session, type) };
  const extra: Partial<GpSession> = { planSum, planPrem };
  if (type === 'N_INC') {
    extra.lifeSum = planSum.N_INC ?? 0;
    extra.lifePrem = planPrem.N_INC ?? 0;
  }
  return extra;
}

export function clampCoverToCaps(session: GpSession, type: NeedType): Partial<GpSession> {
  const caps = coverSliderCaps(session, type);
  const sum = Math.min(planCoverSum(session, type), caps.sum);
  const prem = Math.min(planCoverPrem(session, type), caps.prem);
  if (sum === planCoverSum(session, type) && prem === planCoverPrem(session, type)) return {};
  return setPlanCoverPatch(session, type, { sum, prem });
}

export function sizedCover(session: GpSession, type: NeedType) {
  return { sum: planCoverSum(session, type), prem: planCoverPrem(session, type) };
}

export function defaultWealthMth(session: GpSession, prem?: number): number {
  const wealth = suggestedInGroup(session, 'w');
  if (!wealth.length) return 0;
  const bud = Math.max(0, availableBudget(session) * 12);
  const left = Math.max(0, bud - (prem ?? protectionPremAnnual(session)));
  return Math.max(0, Math.round(left * 0.6 / 12 / wealth.length / 50) * 50);
}

export const FREE_BUDGET_SHARE = 0.5;

export function planAfford(session: GpSession) {
  const available = Math.max(0, availableBudget(session));
  const free = Math.round(available * FREE_BUDGET_SHARE);
  const premYr = protectionPremAnnual(session);
  const premMth = premYr / 12;
  const contribMth = investMthFromPlans(session);
  const monthly = Math.round(contribMth + premMth);
  const investments = session.investments || 0;
  const lumps = investLumpFromPlans(session);
  return {
    available,
    free,
    freePct: Math.round(FREE_BUDGET_SHARE * 100),
    premMth: Math.round(premMth),
    contribMth,
    monthly,
    monthlyOver: monthly - free,
    savings: investments,
    investments,
    lumps,
    lumpOver: lumps - investments,
  };
}
