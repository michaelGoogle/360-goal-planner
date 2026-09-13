import { defaultStressEvents, type GpEvent } from './stressEvents';

export type { GpEvent } from './stressEvents';

export type Route = 'd2cIntro' | 'd2cAbout' | 'd2cMoney' | 'd2cScore' | 'd2cPlan';

export const ROUTES: Route[] = ['d2cIntro', 'd2cAbout', 'd2cMoney', 'd2cScore', 'd2cPlan'];

export const ROUTE_LABEL: Record<Route, string> = {
  d2cIntro: 'Start',
  d2cAbout: 'About you',
  d2cMoney: 'Your money',
  d2cScore: 'Your score',
  d2cPlan: 'Your plan',
};

export type NeedType = 'N_INC' | 'N_CRI' | 'N_TPD' | 'N_RET' | 'N_EDU' | 'N_SAV' | 'N_PRP';
export type ExtraNeed = 'hosp' | 'pa';
export type DepsChoice = '0' | '1' | '2' | '3' | '4+';
export type Prov = 'doc' | 'you';
export type DocKind = 'cpf' | 'bank' | 'pol';

export const NEED_TYPES: NeedType[] = ['N_INC', 'N_CRI', 'N_TPD', 'N_RET', 'N_EDU', 'N_SAV', 'N_PRP'];

export function isNeedType(t: unknown): t is NeedType {
  return typeof t === 'string' && (NEED_TYPES as string[]).includes(t);
}

export interface NeedMeta {
  type: NeedType;
  k: string;
  label: string;
  color: string;
  lo: string;
  hi: string;
  group: 'w' | 'p';
  icon: string;
}

export const NEED_META: Record<NeedType, NeedMeta> = {
  N_INC: {
    type: 'N_INC',
    k: 'life',
    label: 'Income & family protection',
    color: '#7086FD',
    lo: 'Existing cover',
    hi: 'Cover needed',
    group: 'p',
    icon: 'shield',
  },
  N_RET: {
    type: 'N_RET',
    k: 'ret',
    label: 'Retirement',
    color: '#F0952E',
    lo: 'Projected savings',
    hi: 'Amount needed',
    group: 'w',
    icon: 'beach',
  },
  N_SAV: {
    type: 'N_SAV',
    k: 'gs',
    label: 'Savings goal',
    color: '#5B7BD5',
    lo: 'Projected savings',
    hi: 'Amount needed',
    group: 'w',
    icon: 'target',
  },
  N_EDU: {
    type: 'N_EDU',
    k: 'edu',
    label: 'Child’s university education',
    color: '#7B4BC4',
    lo: 'Projected savings',
    hi: 'Amount needed',
    group: 'w',
    icon: 'cap',
  },
  N_PRP: {
    type: 'N_PRP',
    k: 'prp',
    label: 'Property purchase',
    color: '#27AE60',
    lo: 'Projected savings',
    hi: 'Amount needed',
    group: 'w',
    icon: 'house',
  },
  N_CRI: {
    type: 'N_CRI',
    k: 'ci',
    label: 'Critical illness',
    color: '#E8636C',
    lo: 'Existing cover',
    hi: 'Cover needed',
    group: 'p',
    icon: 'heart',
  },
  N_TPD: {
    type: 'N_TPD',
    k: 'dis',
    label: 'Total & permanent disability',
    color: '#F5934A',
    lo: 'Existing cover',
    hi: 'Cover needed',
    group: 'p',
    icon: 'wheel',
  },
};

export const NEED_ICONS: Record<NeedType, string> = {
  N_INC: '🛡️',
  N_CRI: '❤️',
  N_TPD: '♿',
  N_RET: '🏖️',
  N_EDU: '🎓',
  N_SAV: '🎯',
  N_PRP: '🏠',
};

export const EXTRA_NEED_ICONS: Record<ExtraNeed, string> = {
  hosp: '🏨',
  pa: '🩹',
};

export const EXTRA_NEEDS: { k: ExtraNeed; label: string; color: string; icon: string }[] = [
  { k: 'hosp', label: 'Hospitalisation', color: '#4BB6C4', icon: 'hospital' },
  { k: 'pa', label: 'Personal accident', color: '#B07CC6', icon: 'bandage' },
];

export interface NeedRow {
  type: NeedType;
  enabled: boolean;
  needAmount: number;
  existing?: number;
  gap?: number;
  priority?: number;
  weightageScore?: number;
  existingSumAssured?: number | null;
  existingInvestment?: number | null;
  targetYear?: number;
  fundsNeededYear?: number;
  retAge?: number;
  lifestyle?: number;
  region?: string;
  retIncomeMonthly?: number;
  incomeReplaceMonthly?: number;
  dependYears?: number;
  dependants?: number;
  liabilities?: number;
  courseYears?: number;
  childrenToFund?: number;
  monthlyContribution?: number;
  contributeYears?: number;
}

export interface Policy {
  type: string;
  insurer: string;
  sum: number;
  premium: number;
}

export interface DocFile {
  name: string;
  state: 'reading' | 'done';
  src: 'sim' | 'model';
  v: Record<string, string | number>;
}

export interface GpSession {
  name: string;
  age: number | '';
  gender: 'Male' | 'Female';
  residency: 'Singapore Citizen' | 'Permanent Resident' | 'Foreigner';
  nationality: string;
  occupation: string;
  dependents: number;
  depsChoice: DepsChoice;
  dateOfBirth?: string;
  isSmoker: boolean;
  riskProfile: number;
  ageOfRetirement: number;
  incomeMonthly: number;
  expenseMonthly: number;
  cash: number;
  investments: number;
  property: number;
  mortgage: number;
  policies: Policy[];
  needs: NeedRow[];
  extraNeeds: ExtraNeed[];
  events: GpEvent[];
  inflationRate: number;
  interestRate: number;
  incomeGrowthRate: number;
  investmentReturn: number;
  assetReturn: number;
  source?: string;
  note?: string;
  maxStep: number;
  classic: boolean;
  sentence: string;
  sentenceRead: Record<string, string> | null;
  sentenceDirty: boolean;
  sentenceAi: boolean;
  docsOpen: boolean;
  docs: Partial<Record<DocKind, DocFile>>;
  provenance: Partial<Record<string, Prov>>;
  explain: boolean;
  ratAll: boolean;
  ratWhy: string | null;
  tip: string | null;
  touched: Partial<Record<string, true>>;
  moneyTouched: Partial<Record<string, true>>;
  endAge: number;
  lifeOn: boolean;
  investOn: boolean;
  investMth: number;
  investLump: number;
  investRet: number;
  lifeSum: number;
  lifePrem: number;
  criOn: boolean;
  tpdOn: boolean;
  plansOff: NeedType[];
  planMth: Partial<Record<NeedType, number>>;
  planLump: Partial<Record<NeedType, number>>;
  planSum: Partial<Record<NeedType, number>>;
  planPrem: Partial<Record<NeedType, number>>;
  coverMore: boolean;
  prodSeeded: boolean;
  cpfOa: number;
  cpfSa: number;
  cpfMa: number;
  reportMobile?: string;
  reportEmail?: string;
  insapiContactId?: string;
  insapiPlanId?: string;
  reportJobId?: string;
  reportMediaUrl?: string;
  reportVideoStatus?: 'idle' | 'pending' | 'completed' | 'failed';
}

export const EMPTY_SESSION: GpSession = {
  name: '',
  age: '',
  gender: 'Male',
  residency: 'Singapore Citizen',
  nationality: 'Singapore',
  occupation: '',
  dependents: 2,
  depsChoice: '2',
  isSmoker: false,
  riskProfile: 4,
  ageOfRetirement: 65,
  incomeMonthly: 0,
  expenseMonthly: 0,
  cash: 0,
  investments: 0,
  property: 0,
  mortgage: 0,
  policies: [],
  needs: [],
  extraNeeds: [],
  events: defaultStressEvents(),
  inflationRate: 0.023,
  interestRate: 0.012,
  incomeGrowthRate: 0.028,
  investmentReturn: 0.042,
  assetReturn: 0.03,
  maxStep: 0,
  classic: false,
  sentence: '',
  sentenceRead: null,
  sentenceDirty: false,
  sentenceAi: false,
  docsOpen: false,
  docs: {},
  provenance: {},
  explain: false,
  ratAll: false,
  ratWhy: null,
  tip: null,
  touched: {},
  moneyTouched: {},
  endAge: 85,
  lifeOn: true,
  investOn: true,
  investMth: 0,
  investLump: 0,
  investRet: 4.2,
  lifeSum: 0,
  lifePrem: 0,
  criOn: false,
  tpdOn: false,
  plansOff: [],
  planMth: {},
  planLump: {},
  planSum: {},
  planPrem: {},
  coverMore: false,
  prodSeeded: false,
  cpfOa: 0,
  cpfSa: 0,
  cpfMa: 0,
};

export function money(n: number): string {
  const v = Math.round(n);
  if (!Number.isFinite(v)) return '—';
  return (v < 0 ? '−S$' : 'S$') + Math.abs(v).toLocaleString('en-SG');
}

export function moneyK(n: number): string {
  const v = Math.round(n);
  if (!Number.isFinite(v)) return '—';
  if (Math.abs(v) >= 1e6) {
    const m = v / 1e6;
    const s = m.toFixed(1).replace(/\.0$/, '');
    return (v < 0 ? '−S$' : 'S$') + s + 'm';
  }
  if (Math.abs(v) >= 1000) return (v < 0 ? '−S$' : 'S$') + Math.round(Math.abs(v) / 1000) + 'k';
  return money(v);
}

export function happiBand(v: number): 'POOR' | 'FAIR' | 'GOOD' {
  if (v >= 85) return 'GOOD';
  if (v >= 50) return 'FAIR';
  return 'POOR';
}

export function happiCaption(v: number): string {
  const band = happiBand(v);
  if (band === 'GOOD') return 'Good: You are well covered. Protect what you already have.';
  if (band === 'FAIR') return 'Fair: A solid start. Close the largest gaps to lift this.';
  return 'Poor: Start with the biggest shortfall, not everything at once.';
}

export const HAPPI_COL = { POOR: '#E5484D', FAIR: '#E8912B', GOOD: '#12A150' } as const;
export const HAPPI_TINT = { POOR: '#FDEDED', FAIR: '#FEF4E6', GOOD: '#E8F8EF' } as const;
export const HAPPI_INK = { POOR: '#B4242A', FAIR: '#9A5D06', GOOD: '#0B7A3B' } as const;

export const POLICY_TYPES = [
  'Life Protection',
  'Critical Illness',
  'Permanent Disability',
  'Hospitalisation',
  'Personal Accident',
] as const;

export const POLICY_COL: Record<string, string> = {
  'Life Protection': '#7086FD',
  'Critical Illness': '#E8636C',
  'Permanent Disability': '#F5934A',
  Hospitalisation: '#4BB6C4',
  'Personal Accident': '#F0952E',
  Education: '#7B4BC4',
};

export function depsFromChoice(c: DepsChoice): number {
  return c === '4+' ? 5 : Number(c);
}

export function choiceFromDeps(n: number): DepsChoice {
  if (n >= 4) return '4+';
  if (n <= 0) return '0';
  return String(n) as DepsChoice;
}

export function sessionAge(s: Pick<GpSession, 'age'>): number | null {
  return typeof s.age === 'number' && s.age >= 18 && s.age <= 70 ? s.age : null;
}

export function cpfOn(s: Pick<GpSession, 'residency'>): boolean {
  return s.residency !== 'Foreigner';
}

/** Ordinary wage ceiling from 1 Jan 2026. 20% employee rate → max S$1,600. */
export const CPF_OW_CEILING = 8000;

export function employeeCpfRate(age: number, residency: string): number {
  if (residency === 'Foreigner') return 0;
  if (age <= 55) return 0.2;
  if (age <= 60) return 0.15;
  if (age <= 65) return 0.095;
  return 0.05;
}

export function employeeCpfMonthly(
  s: Pick<GpSession, 'incomeMonthly' | 'residency' | 'age'>,
): number {
  const age = sessionAge(s) ?? (typeof s.age === 'number' ? s.age : 40);
  const rate = employeeCpfRate(age, s.residency);
  const gross = s.incomeMonthly || 0;
  if (rate <= 0 || gross <= 0) return 0;
  return Math.floor(Math.min(gross, CPF_OW_CEILING) * rate);
}

export function takeHomeMonthly(s: Pick<GpSession, 'incomeMonthly' | 'residency' | 'age'>): number {
  return Math.max(0, (s.incomeMonthly || 0) - employeeCpfMonthly(s));
}

/** 0 dependants → 67.5% of take-home; +5pp each; cap 90%. */
export function spendShare(dependents: number): number {
  const deps = Math.max(0, Math.floor(dependents || 0));
  return Math.min(0.675 + 0.05 * deps, 0.9);
}

export function spendSharePct(dependents: number): number {
  return Math.round(spendShare(dependents) * 1000) / 10;
}

export function availableBudget(s: Pick<GpSession, 'incomeMonthly' | 'expenseMonthly' | 'residency' | 'age'>): number {
  return takeHomeMonthly(s) - (s.expenseMonthly || 0);
}

export function chartMoneyOut(s: Pick<GpSession, 'incomeMonthly' | 'expenseMonthly' | 'residency' | 'age'>): number {
  return (s.expenseMonthly || 0) + employeeCpfMonthly(s);
}

export function d2cReady(s: GpSession): boolean {
  return !!(String(s.name || '').trim() && sessionAge(s) && s.occupation && s.gender && s.residency);
}

export function firstName(s: Pick<GpSession, 'name'>): string {
  const n = String(s.name || '').trim().split(/\s+/)[0];
  return n || 'you';
}

export function liquid(s: Pick<GpSession, 'cash' | 'investments'>): number {
  return (s.cash || 0) + (s.investments || 0);
}

export function assets(s: Pick<GpSession, 'cash' | 'investments' | 'property'>): number {
  return liquid(s) + (s.property || 0);
}

export function netWealth(s: Pick<GpSession, 'cash' | 'investments' | 'property' | 'mortgage'>): number {
  return assets(s) - (s.mortgage || 0);
}

export function coverSum(s: Pick<GpSession, 'policies'>): number {
  return s.policies.reduce((t, p) => t + (p.sum || 0), 0);
}

export function coverPrem(s: Pick<GpSession, 'policies'>): number {
  return s.policies.reduce((t, p) => t + (p.premium || 0), 0);
}

export function needHave(s: GpSession, n: NeedRow): number {
  if (n.existing != null && n.existing > 0) return n.existing;
  if (n.existingSumAssured != null && n.existingSumAssured > 0) return n.existingSumAssured;
  if (n.existingInvestment != null && n.existingInvestment > 0) return n.existingInvestment;
  if (n.type === 'N_INC' || n.type === 'N_CRI' || n.type === 'N_TPD') {
    const want =
      n.type === 'N_INC' ? 'Life Protection' : n.type === 'N_CRI' ? 'Critical Illness' : 'Permanent Disability';
    return s.policies.filter(p => p.type === want).reduce((t, p) => t + p.sum, 0);
  }
  return liquid(s);
}

export function needGap(s: GpSession, n: NeedRow): number {
  return Math.max(0, (n.needAmount || 0) - needHave(s, n));
}

export function barWidths(values: number[]): number[] {
  const tot = values.reduce((a, v) => a + Math.abs(v || 0), 0) || 1;
  return values.map(v => (Math.abs(v || 0) / tot) * 100);
}
