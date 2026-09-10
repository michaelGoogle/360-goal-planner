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
  /** Absolute magnitude of v (frac 0–1, or dollars). */
  vMin: number;
  vMax: number;
  vStep: number;
  frac: boolean;
}

const W = '#FB8C00';
const P = '#7086FD';

const FRAC = { vMin: 0, vMax: 0.8, vStep: 0.01, frac: true as const };
const INFL = { vMin: 0, vMax: 0.15, vStep: 0.005, frac: true as const };
const CCY = { vMin: 0, vMax: 0.5, vStep: 0.01, frac: true as const };
const LUMP = { vMin: 0, vMax: 200_000, vStep: 5_000, frac: false as const };
const CARE = { vMin: 0, vMax: 300_000, vStep: 1_000, frac: false as const };
const BABY = { vMin: 0, vMax: 200_000, vStep: 1_000, frac: false as const };

export const STRESS_EVENTS: StressSpec[] = [
  { id: 'crash', label: 'Market crash', kind: 'one', group: 'w', valueLabel: 'Asset shock', defaultV: 0.35, defaultYear: 8, icon: 'crash', color: W, ...FRAC },
  { id: 'ccy', label: 'Currency shock', kind: 'one', group: 'w', valueLabel: 'Depreciation on foreign holdings', defaultV: 0.14, defaultYear: 6, icon: 'money', color: W, ...CCY },
  { id: 'infl', label: 'Inflation shock', kind: 'range', group: 'w', valueLabel: 'Additional inflation', defaultV: 0.03, defaultYear: [4, 9], icon: 'flame', color: W, ...INFL },
  { id: 'inc', label: 'Impact on income', kind: 'range', group: 'w', valueLabel: 'Impact', defaultV: -0.2, defaultYear: [5, 10], icon: 'wage', color: W, ...FRAC },
  { id: 'death', label: 'Death', kind: 'one', group: 'p', valueLabel: 'One-time cost', defaultV: 20000, defaultYear: 17, icon: 'heart', color: P, ...LUMP },
  { id: 'ci', label: 'Critical illness', kind: 'one', group: 'p', valueLabel: 'One-time medical cost', defaultV: 150000, defaultYear: 12, icon: 'cross', color: P, ...LUMP },
  { id: 'tpd', label: 'Total & permanent disability', kind: 'one', group: 'p', valueLabel: 'One-time medical cost', defaultV: 200000, defaultYear: 15, icon: 'wheel', color: P, ...LUMP },
  { id: 'pa', label: 'Personal accident', kind: 'one', group: 'p', valueLabel: 'One-time medical cost', defaultV: 80000, defaultYear: 10, icon: 'bolt', color: P, ...LUMP },
  { id: 'hosp', label: 'Hospitalisation', kind: 'one', group: 'p', valueLabel: 'One-time hospital bill', defaultV: 120000, defaultYear: 9, icon: 'hospital', color: P, ...LUMP },
  { id: 'care', label: 'Long-term care years', kind: 'rangec', group: 'p', valueLabel: 'Additional annual care cost', defaultV: 90000, defaultYear: [30, 35], icon: 'care', color: P, ...CARE },
  { id: 'wed', label: 'Wedding / marriage', kind: 'one', group: 'p', valueLabel: 'One-time cost', defaultV: 60000, defaultYear: 5, icon: 'rings', color: P, ...LUMP },
  { id: 'baby', label: 'Newborn', kind: 'one', group: 'p', valueLabel: 'One-time newborn cost', defaultV: 35000, defaultYear: 3, icon: 'baby', color: P, ...BABY },
  { id: 'exp', label: 'Impact on expenses', kind: 'range', group: 'p', valueLabel: 'Impact', defaultV: 0.15, defaultYear: [6, 12], icon: 'cart', color: P, ...FRAC },
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

/** Year offsets are from current age; 80 covers a full working-to-end-age span. */
export const STRESS_YEAR_CAP = 80;

function clampNum(n: number, min: number, max: number): number {
  if (!Number.isFinite(n)) return min;
  return Math.min(max, Math.max(min, n));
}

export function clampEvent(ev: GpEvent, last: number): GpEvent {
  const spec = STRESS_BY_ID[ev.id];
  const hi = Math.max(1, last);
  const year = clampNum(ev.year, 0, hi);
  let from = clampNum(ev.from, 0, hi);
  let to = clampNum(ev.to, 0, hi);
  if (from > to) {
    const t = from;
    from = to;
    to = t;
  }
  const mag = spec ? clampNum(Math.abs(ev.v), spec.vMin, spec.vMax) : ev.v;
  const v = spec && spec.defaultV < 0 ? -mag : mag;
  return { ...ev, year, from, to, v };
}

function fromSpec(spec: StressSpec): GpEvent {
  const span = spec.defaultYear;
  if (Array.isArray(span)) {
    return { id: spec.id, on: false, year: span[0], from: span[0], to: span[1], v: spec.defaultV, label: spec.label };
  }
  return { id: spec.id, on: false, year: span, from: span, to: span, v: spec.defaultV, label: spec.label };
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
    return clampEvent(
      {
        ...base,
        on: !!prev.on,
        year: Number.isFinite(prev.year) ? prev.year : base.year,
        from: Number.isFinite(prev.from) ? prev.from : (Number.isFinite(prev.year) ? prev.year : base.from),
        to: Number.isFinite(prev.to) ? prev.to : (Number.isFinite(prev.year) ? prev.year : base.to),
        v: Number.isFinite(prev.v) ? prev.v : base.v,
        label: spec.label,
      },
      STRESS_YEAR_CAP,
    );
  });
}

export function eventAge(startAge: number, offset: number, last: number): number {
  return startAge + Math.max(0, Math.min(last, offset));
}

export function formatEventValue(v: number, spec?: StressSpec): string {
  if (spec ? spec.frac : Math.abs(v) <= 1) {
    return `${Math.round(Math.abs(v) * 100)}%`;
  }
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
    PTD: 'PTD',
    pa: 'PersonalAccident',
    PersonalAccident: 'PersonalAccident',
    inc: 'Income',
    Unemployment: 'Income',
    infl: 'Inflation',
    Inflation: 'Inflation',
    hosp: 'Hospitalization',
    care: 'Expense',
    wed: 'Marriage',
    baby: 'Newborn',
    exp: 'Expense',
    ccy: 'CurrencyShock',
  };
  return mapped[id] || id;
}
