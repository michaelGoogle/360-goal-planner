import { investRetFromReturn } from './assumptions';
import { clampRiskProfile, riskLevel, type RiskProfile } from './riskBand';
import type { GpSession } from './types';

export { clampRiskProfile, riskLevel, RISK_LEVELS, RISK_TRACK_GRADIENT } from './riskBand';
export type { RiskBand, RiskLevel, RiskProfile } from './riskBand';

const W_LIQ = 0.25;
const W_DSR = 0.2;
const W_DAR = 0.15;
const W_SAV = 0.15;
const W_HOR = 0.15;
const W_DEP = 0.1;

const SUGGEST: Record<RiskProfile, number> = {
  1: 0.03,
  2: 0.035,
  3: 0.042,
  4: 0.05,
  5: 0.055,
};

const CEILING: Record<RiskProfile, number> = {
  1: 0.042,
  2: 0.05,
  3: 0.055,
  4: 0.06,
  5: 0.065,
};

export const RISK_ABILITY_TIP =
  'Risk ability is what volatility your cash, debt, spending, and years to retirement can absorb. It is calculated from Your money, not a free slider. Risk tolerance is how much market swing you say you can sit with. The plan uses the lower of the two — never the higher, and never a return that would close a shortfall.';

export interface RiskFactors {
  liquidityMonths: number;
  dsr: number;
  dar: number;
  savingsRatio: number;
  horizonYears: number;
  dependants: number;
  liquidityPts: number;
  dsrPts: number;
  darPts: number;
  savingsPts: number;
  horizonPts: number;
  dependantsPts: number;
}

export interface RiskCapacity {
  factors: RiskFactors;
  raw: number;
  rounded: RiskProfile;
  capacity: RiskProfile;
  /** Strictest hard-cap reason, if a cap applied. */
  capReason: string | null;
}

export function liquidityMonths(cash: number, expense: number): number {
  if (!(expense > 0)) return 0;
  return (cash || 0) / expense;
}

export function debtServiceRatio(mortgage: number, income: number): number {
  const pay = (mortgage || 0) / 240;
  if (!(income > 0)) return mortgage > 0 ? Number.POSITIVE_INFINITY : 0;
  return pay / income;
}

export function debtAssetRatio(
  mortgage: number,
  cash: number,
  investments: number,
  property: number,
): number {
  const assets = (cash || 0) + (investments || 0) + (property || 0);
  if (!(assets > 0)) return mortgage > 0 ? Number.POSITIVE_INFINITY : 0;
  return (mortgage || 0) / assets;
}

export function savingsRatio(income: number, expense: number): number {
  if (!(income > 0)) return Number.NEGATIVE_INFINITY;
  return (income - (expense || 0)) / income;
}

export function horizonYears(age: number | '', retireAge: number): number {
  const a = typeof age === 'number' && age > 0 ? age : 0;
  if (!(a > 0)) return 0;
  return Math.max(0, (retireAge || 65) - a);
}

function ptsLiquidity(months: number, expenseOk: boolean): number {
  if (!expenseOk) return 1;
  if (months < 1) return 1;
  if (months < 3) return 2;
  if (months < 6) return 3;
  if (months < 12) return 4;
  return 5;
}

function ptsSavings(ratio: number, incomeOk: boolean): number {
  if (!incomeOk) return 1;
  if (ratio < 0) return 1;
  if (ratio < 0.1) return 2;
  if (ratio < 0.2) return 3;
  if (ratio < 0.3) return 4;
  return 5;
}

function ptsDsr(dsr: number): number {
  if (dsr > 0.5) return 1;
  if (dsr >= 0.35) return 2;
  if (dsr >= 0.2) return 3;
  if (dsr > 0.1) return 4;
  return 5;
}

function ptsDar(dar: number): number {
  if (dar > 0.7) return 1;
  if (dar >= 0.5) return 2;
  if (dar >= 0.3) return 3;
  if (dar > 0.15) return 4;
  return 5;
}

function ptsHorizon(years: number, ageKnown: boolean): number {
  if (!ageKnown) return 1;
  if (years < 5) return 1;
  if (years < 10) return 2;
  if (years < 20) return 3;
  if (years < 30) return 4;
  return 5;
}

function ptsDependants(n: number): number {
  const d = Math.max(0, Math.floor(n || 0));
  if (d <= 0) return 5;
  if (d === 1) return 4;
  if (d === 2) return 3;
  if (d === 3) return 2;
  return 1;
}

function clampProfile(n: number): RiskProfile {
  const r = Math.round(n);
  if (!Number.isFinite(r)) return 3;
  return Math.min(5, Math.max(1, r)) as RiskProfile;
}

interface HardCap {
  limit: 1 | 2 | 3;
  reason: string;
}

function hardCaps(liq: number, dsr: number, dar: number, horizon: number): HardCap[] {
  const caps: HardCap[] = [];
  if (liq < 1) {
    caps.push({
      limit: 1,
      reason: 'Cash below 1 month of spending caps risk ability at Low.',
    });
  } else if (liq < 3) {
    caps.push({
      limit: 2,
      reason: 'Cash below 3 months of spending caps risk ability at Low-Medium.',
    });
  }
  if (dsr > 0.5 || dar > 0.7) {
    caps.push({
      limit: 2,
      reason: 'High debt caps risk ability at Low-Medium.',
    });
  } else if (dsr > 0.35 || dar > 0.5) {
    caps.push({
      limit: 3,
      reason: 'Debt service or leverage caps risk ability at Medium.',
    });
  }
  if (horizon < 5) {
    caps.push({
      limit: 2,
      reason: 'Fewer than 5 years to retirement caps risk ability at Low-Medium.',
    });
  } else if (horizon < 10) {
    caps.push({
      limit: 3,
      reason: 'Fewer than 10 years to retirement caps risk ability at Medium.',
    });
  }
  return caps;
}

export function riskCapacity(
  session: Pick<
    GpSession,
    | 'age'
    | 'ageOfRetirement'
    | 'dependents'
    | 'incomeMonthly'
    | 'expenseMonthly'
    | 'cash'
    | 'investments'
    | 'property'
    | 'mortgage'
  >,
): RiskCapacity {
  const income = session.incomeMonthly || 0;
  const expense = session.expenseMonthly || 0;
  const cash = session.cash || 0;
  const liq = liquidityMonths(cash, expense);
  const dsr = debtServiceRatio(session.mortgage || 0, income);
  const dar = debtAssetRatio(session.mortgage || 0, cash, session.investments || 0, session.property || 0);
  const sav = savingsRatio(income, expense);
  const ageKnown = typeof session.age === 'number' && session.age > 0;
  const hor = horizonYears(session.age, session.ageOfRetirement || 65);
  const deps = session.dependents || 0;

  const factors: RiskFactors = {
    liquidityMonths: liq,
    dsr,
    dar,
    savingsRatio: Number.isFinite(sav) ? sav : 0,
    horizonYears: hor,
    dependants: deps,
    liquidityPts: ptsLiquidity(liq, expense > 0),
    dsrPts: ptsDsr(dsr),
    darPts: ptsDar(dar),
    savingsPts: ptsSavings(sav, income > 0),
    horizonPts: ptsHorizon(hor, ageKnown),
    dependantsPts: ptsDependants(deps),
  };

  const raw =
    W_LIQ * factors.liquidityPts +
    W_DSR * factors.dsrPts +
    W_DAR * factors.darPts +
    W_SAV * factors.savingsPts +
    W_HOR * factors.horizonPts +
    W_DEP * factors.dependantsPts;
  const rounded = clampProfile(raw);
  const caps = hardCaps(liq, dsr, dar, hor);
  const strictest = caps.reduce<HardCap | null>((best, cap) => {
    if (!best || cap.limit < best.limit) return cap;
    return best;
  }, null);
  const capacity = strictest ? (Math.min(rounded, strictest.limit) as RiskProfile) : rounded;
  const capReason = strictest && rounded >= strictest.limit ? strictest.reason : null;

  return { factors, raw, rounded, capacity, capReason };
}

export function suitableRisk(capacity: number, tolerance: number): RiskProfile {
  return Math.min(clampRiskProfile(capacity), clampRiskProfile(tolerance)) as RiskProfile;
}

export function suggestedNetReturn(band: number): number {
  return SUGGEST[clampRiskProfile(band)];
}

export function netReturnCeiling(band: number): number {
  return CEILING[clampRiskProfile(band)];
}

/** Note when the slider is above the band's soft ceiling. `rate` is a fraction (0.042). */
export function netReturnCeilingNote(rate: number, band: number): string | null {
  const ceil = netReturnCeiling(band);
  if (!(rate > ceil + 1e-9)) return null;
  return `Above the ${(ceil * 100).toFixed(1)}% soft ceiling for ${riskLevel(band).label}. Allowed — the colour is the warning.`;
}

export function hasMoneyInputs(
  session: Pick<GpSession, 'incomeMonthly' | 'expenseMonthly' | 'cash' | 'investments' | 'property' | 'mortgage'>,
): boolean {
  return (
    (session.incomeMonthly || 0) > 0 ||
    (session.expenseMonthly || 0) > 0 ||
    (session.cash || 0) > 0 ||
    (session.investments || 0) > 0 ||
    (session.property || 0) > 0 ||
    (session.mortgage || 0) > 0
  );
}

/** Derived session fields: suitable HU profile and optional suggested net return. */
export function riskSessionPatch(session: GpSession): Partial<GpSession> {
  const cap = riskCapacity(session);
  const tolerance = clampRiskProfile(session.riskTolerance ?? 3);
  const band = suitableRisk(cap.capacity, tolerance);
  const patch: Partial<GpSession> = { riskProfile: band, riskTolerance: tolerance };
  if (!session.investmentReturnTouched && hasMoneyInputs(session)) {
    const rate = suggestedNetReturn(band);
    if (Math.round((session.investmentReturn || 0) * 1000) !== Math.round(rate * 1000)) {
      patch.investmentReturn = rate;
      patch.investRet = investRetFromReturn(rate);
    }
  }
  return patch;
}

export function sessionRiskBand(
  session: Pick<GpSession, 'riskTolerance'> & Parameters<typeof riskCapacity>[0],
): RiskProfile {
  return suitableRisk(riskCapacity(session).capacity, session.riskTolerance ?? 3);
}
