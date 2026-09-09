/** Unforeseen events catalog — same 13 rows as the HTML SVEV list. */

export type EventKind = 'one' | 'range' | 'rangec';
export type EventGroup = 'w' | 'p';

export interface GpEvent {
  id: string;
  on: boolean;
  year: number;
  from: number;
  to: number;
  v: number;
  label: string;
}

export interface StressSpec {
  id: string;
  label: string;
  kind: EventKind;
  group: EventGroup;
  valueLabel: string;
  defaultV: number;
  defaultYear: number | [number, number];
  icon: string;
  color: string;
}

const W = '#FB8C00';
const P = '#7086FD';

export const STRESS_EVENTS: StressSpec[] = [
  { id: 'crash', label: 'Market crash', kind: 'one', group: 'w', valueLabel: 'Asset shock', defaultV: 0.35, defaultYear: 8, icon: 'crash', color: W },
  { id: 'ccy', label: 'Currency shock', kind: 'one', group: 'w', valueLabel: 'Depreciation on foreign holdings', defaultV: 0.14, defaultYear: 6, icon: 'money', color: W },
  { id: 'infl', label: 'Inflation shock', kind: 'range', group: 'w', valueLabel: 'Additional inflation', defaultV: 0.03, defaultYear: [4, 9], icon: 'flame', color: W },
  { id: 'inc', label: 'Impact on income', kind: 'range', group: 'w', valueLabel: 'Impact', defaultV: -0.2, defaultYear: [5, 10], icon: 'wage', color: W },
  { id: 'death', label: 'Death', kind: 'one', group: 'p', valueLabel: 'One-time cost', defaultV: 20000, defaultYear: 17, icon: 'heart', color: P },
  { id: 'ci', label: 'Critical illness', kind: 'one', group: 'p', valueLabel: 'One-time medical cost', defaultV: 150000, defaultYear: 12, icon: 'cross', color: P },
  { id: 'tpd', label: 'Total & permanent disability', kind: 'one', group: 'p', valueLabel: 'One-time medical cost', defaultV: 200000, defaultYear: 15, icon: 'wheel', color: P },
  { id: 'pa', label: 'Personal accident', kind: 'one', group: 'p', valueLabel: 'One-time medical cost', defaultV: 80000, defaultYear: 10, icon: 'bolt', color: P },
  { id: 'hosp', label: 'Hospitalisation', kind: 'one', group: 'p', valueLabel: 'One-time hospital bill', defaultV: 120000, defaultYear: 9, icon: 'hospital', color: P },
  { id: 'care', label: 'Long-term care years', kind: 'rangec', group: 'p', valueLabel: 'Additional annual care cost', defaultV: 90000, defaultYear: [30, 35], icon: 'care', color: P },
  { id: 'wed', label: 'Wedding / marriage', kind: 'one', group: 'p', valueLabel: 'One-time cost', defaultV: 60000, defaultYear: 5, icon: 'rings', color: P },
  { id: 'baby', label: 'Newborn', kind: 'one', group: 'p', valueLabel: 'One-time newborn cost', defaultV: 35000, defaultYear: 3, icon: 'baby', color: P },
  { id: 'exp', label: 'Impact on expenses', kind: 'range', group: 'p', valueLabel: 'Impact', defaultV: 0.15, defaultYear: [6, 12], icon: 'cart', color: P },
];

const ALIAS: Record<string, string> = {
  Crash: 'crash',
  MarketCrash: 'crash',
  Death: 'death',
  CI: 'ci',
  PTD: 'tpd',
  Disability: 'tpd',
  PersonalAccident: 'pa',
  Unemployment: 'inc',
  Inflation: 'infl',
};

export const STRESS_BY_ID: Record<string, StressSpec> = Object.fromEntries(STRESS_EVENTS.map(s => [s.id, s]));

export function isFracValue(v: number): boolean {
  return Math.abs(v) <= 1;
}

function fromSpec(spec: StressSpec): GpEvent {
  const span = Array.isArray(spec.defaultYear);
  const year = span ? spec.defaultYear[0] : spec.defaultYear;
  const from = span ? spec.defaultYear[0] : year;
  const to = span ? spec.defaultYear[1] : year;
  return { id: spec.id, on: false, year, from, to, v: spec.defaultV, label: spec.label };
}

export function defaultStressEvents(): GpEvent[] {
  return STRESS_EVENTS.map(fromSpec);
}

export function hydrateStressEvents(raw: GpEvent[] | undefined): GpEvent[] {
  const byId = new Map<string, GpEvent>();
  for (const ev of raw || []) {
    const id = ALIAS[ev.id] || ev.id;
    byId.set(id, { ...ev, id });
  }
  return STRESS_EVENTS.map(spec => {
    const prev = byId.get(spec.id);
    const base = fromSpec(spec);
    if (!prev) return base;
    return {
      ...base,
      on: !!prev.on,
      year: Number.isFinite(prev.year) ? prev.year : base.year,
      from: Number.isFinite(prev.from) ? prev.from : (Number.isFinite(prev.year) ? prev.year : base.from),
      to: Number.isFinite(prev.to) ? prev.to : (Number.isFinite(prev.year) ? prev.year : base.to),
      v: Number.isFinite(prev.v) ? prev.v : base.v,
      label: spec.label,
    };
  });
}

export function eventAge(startAge: number, offset: number, last: number): number {
  return startAge + Math.max(0, Math.min(last, offset));
}

export function formatEventValue(v: number): string {
  if (isFracValue(v)) return `${Math.round(Math.abs(v) * 100)}%`;
  return `S$${Math.round(Math.abs(v)).toLocaleString('en-US')}`;
}

/** Ids SV already understands, plus the rest of the catalog. */
export function svEventType(id: string): string {
  const mapped: Record<string, string> = {
    crash: 'MarketCrash',
    Crash: 'MarketCrash',
    death: 'Death',
    Death: 'Death',
    ci: 'CI',
    CI: 'CI',
    tpd: 'PTD',
    pa: 'PersonalAccident',
    inc: 'Unemployment',
    Unemployment: 'Unemployment',
    infl: 'Inflation',
    Inflation: 'Inflation',
    hosp: 'Hospitalisation',
    care: 'LongTermCare',
    wed: 'Wedding',
    baby: 'Newborn',
    exp: 'ExpenseShock',
    ccy: 'CurrencyShock',
  };
  return mapped[id] || id;
}
