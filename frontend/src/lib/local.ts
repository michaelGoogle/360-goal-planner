import { depsFromChoice, type DepsChoice, type DocKind, type GpSession, type NeedType } from './types';
import type { ParsedSentence } from './parse';
import { investRetFromReturn } from './assumptions';
import { coverSliderCaps, defaultWealthMth, investLumpFromPlans, investMthFromPlans, planSliderCaps, productFlags, suggestedInGroup } from './planProducts';

const OCC_PATTERNS: [RegExp, number][] = [
  [/surgeon|medical specialist|investment banker|private banker|chief |actuar|fund manager|portfolio manager/i, 18000],
  [/doctor|lawyer|legal counsel|dentist|pilot|general manager|director|real estate developer|stockbroker|trader/i, 13500],
  [
    /architect|scientist|risk manager|financial controller|solutions architect|professor|economist|data scientist|product manager|programme manager|supply chain|compliance/i,
    10500,
  ],
  [
    /manager|engineer|analyst|developer|consultant|pharmac|lecturer|owner|entrepreneur|surveyor|auditor|accountant|veterinar|psycholog/i,
    8200,
  ],
  [
    /nurse|teacher|designer|officer|therapist|technician|executive|adviser|agent|paralegal|journalist|radiograph|social worker|midwife/i,
    5800,
  ],
  [/assistant|clerk|driver|retail|barista|cleaner|waiter|security|courier|baker|hairdress|receptionist|tailor|welder/i, 3400],
  [/student/i, 1400],
  [/retired|homemaker/i, 2400],
];

export interface Derive {
  a: number;
  occ: string;
  band: number;
  curve: number;
  resF: number;
  inc: number;
  expPct: number;
  exp: number;
  yrs: number;
  generic: boolean;
}

export function deriveFromSession(session: GpSession): Derive {
  const a = typeof session.age === 'number' ? session.age : 35;
  const o = String(session.occupation || '').toLowerCase();
  let band = 5600;
  for (const [re, v] of OCC_PATTERNS) {
    if (re.test(o)) {
      band = v;
      break;
    }
  }
  const curve = a <= 25 ? 0.72 : a >= 52 ? 1.62 : 0.72 + (Math.min(a, 52) - 25) * 0.0333;
  const resF = session.residency === 'Foreigner' ? 1.06 : 1;
  const inc = Math.round((band * curve * resF) / 50) * 50;
  const expPct = a < 30 ? 0.74 : a < 45 ? 0.64 : 0.57;
  return {
    a,
    occ: session.occupation || '',
    band,
    curve,
    resF,
    inc,
    expPct,
    exp: Math.round((inc * expPct) / 50) * 50,
    yrs: Math.max(0, a - 24),
    generic: !o || band === 5600,
  };
}

export function docSim(kind: DocKind, session: GpSession): Record<string, string | number> {
  const a = typeof session.age === 'number' ? session.age : 42;
  const base = deriveFromSession(session).inc || 8000;
  const yrs = Math.max(1, a - 24);
  const r = (v: number) => Math.round(v / 100) * 100;
  if (kind === 'cpf') {
    const on = session.residency !== 'Foreigner';
    return {
      oa: on ? r(base * 0.23 * 12 * yrs * 0.42) : 0,
      sa: on ? r(base * 0.06 * 12 * yrs * 1.35) : 0,
      ma: on ? Math.min(79000, r(base * 0.08 * 12 * yrs * 0.95)) : 0,
    };
  }
  if (kind === 'bank') return { cash: r(base * 5.5 + yrs * 2400), investments: r(yrs * yrs * 1150) };
  return {
    type: 'Life Protection',
    insurer: 'Great Eastern',
    sum: Math.round((base * 12 * 7) / 10000) * 10000,
    premium: Math.round((base * 12 * 7 * 0.0042) / 10) * 10,
  };
}

export function parsedToSession(got: ParsedSentence): Partial<GpSession> {
  const out: Partial<GpSession> = { touched: {} };
  const touched: Partial<Record<string, true>> = {};
  if (got.name) {
    out.name = got.name;
    touched.name = true;
  }
  if (got.age) {
    out.age = Number(got.age);
    touched.age = true;
  }
  if (got.gender) {
    out.gender = got.gender;
    touched.gender = true;
  }
  if (got.res) {
    out.residency = got.res;
    touched.res = true;
  }
  if (got.deps) {
    out.depsChoice = got.deps as DepsChoice;
    out.dependents = depsFromChoice(got.deps as DepsChoice);
    touched.deps = true;
  }
  if (got.occ) {
    out.occupation = got.occ;
    touched.occ = true;
  }
  out.touched = touched;
  const read: Record<string, string> = {};
  if (got.name) read.name = got.name;
  if (got.age) read.age = got.age;
  if (got.gender) read.gender = got.gender;
  if (got.deps) read.deps = got.deps;
  if (got.res) read.res = got.res;
  if (got.occ) read.occ = got.occ;
  out.sentenceRead = Object.keys(read).length ? read : null;
  out.sentenceDirty = false;
  return out;
}

export function applyDocs(session: GpSession): GpSession {
  const next = { ...session, provenance: { ...session.provenance }, policies: [...session.policies] };
  const bank = session.docs.bank;
  if (bank?.state === 'done' && bank.v) {
    if (!session.moneyTouched.cash && !session.moneyTouched.savings) {
      next.cash = Math.max(0, Math.round(Number(bank.v.cash) || 0));
      next.provenance.cash = 'doc';
    }
    if (!session.moneyTouched.investments && !session.moneyTouched.savings) {
      next.investments = Math.max(0, Math.round(Number(bank.v.investments) || 0));
      next.provenance.investments = 'doc';
    }
  }
  const pol = session.docs.pol;
  if (pol?.state === 'done' && pol.v && Number(pol.v.sum) > 0) {
    const type = String(pol.v.type || 'Life Protection');
    next.policies = [
      ...next.policies.filter(p => p.type !== type),
      {
        type,
        insurer: String(pol.v.insurer || 'My insurer'),
        sum: Math.max(0, Math.round(Number(pol.v.sum) || 0)),
        premium: Math.max(0, Math.round(Number(pol.v.premium) || 0)),
      },
    ];
    next.provenance.cover = 'doc';
  }
  const cpf = session.docs.cpf;
  if (cpf?.state === 'done' && cpf.v) {
    next.cpfOa = Math.max(0, Math.round(Number(cpf.v.oa) || 0));
    next.cpfSa = Math.max(0, Math.round(Number(cpf.v.sa) || 0));
    next.cpfMa = Math.max(0, Math.round(Number(cpf.v.ma) || 0));
  }
  return next;
}

function seedCoverDefaults(session: GpSession) {
  const planSum: Partial<Record<NeedType, number>> = { ...session.planSum };
  const planPrem: Partial<Record<NeedType, number>> = { ...session.planPrem };
  let patched = false;
  for (const n of suggestedInGroup(session, 'p')) {
    const caps = coverSliderCaps(session, n.type);
    if (planSum[n.type] == null) {
      planSum[n.type] = caps.sum;
      patched = true;
    }
    if (planPrem[n.type] == null) {
      planPrem[n.type] = Math.round(caps.prem / 2 / 10) * 10;
      patched = true;
    }
  }
  return {
    planSum,
    planPrem,
    patched,
    lifeSum: planSum.N_INC ?? session.lifeSum,
    lifePrem: planPrem.N_INC ?? session.lifePrem,
  };
}

export function seedProducts(session: GpSession): Partial<GpSession> {
  const flags = productFlags(session);
  const cover = seedCoverDefaults(session);
  if (session.prodSeeded) {
    return {
      ...flags,
      investMth: investMthFromPlans(session),
      investLump: investLumpFromPlans(session),
      ...(cover.patched
        ? { planSum: cover.planSum, planPrem: cover.planPrem, lifeSum: cover.lifeSum, lifePrem: cover.lifePrem }
        : {}),
    };
  }
  const investRet = investRetFromReturn(session.investmentReturn || 0.042);
  const { planSum, planPrem, lifePrem } = cover;
  const share = defaultWealthMth({ ...session, ...flags, planSum, planPrem });
  const planMth: Partial<Record<NeedType, number>> = { ...session.planMth };
  const planLump: Partial<Record<NeedType, number>> = { ...session.planLump };
  const sized = { ...session, ...flags, investRet, planMth, planLump };
  for (const n of suggestedInGroup(session, 'w')) {
    const monthlyCap = planSliderCaps(sized, n.type).monthly;
    if (planMth[n.type] == null) planMth[n.type] = Math.min(share, monthlyCap);
    if (planLump[n.type] == null) planLump[n.type] = 0;
  }
  const next = { ...session, ...flags, planMth, planLump };
  return {
    prodSeeded: true,
    ...flags,
    lifeSum: cover.lifeSum,
    lifePrem,
    investLump: investLumpFromPlans(next),
    investMth: investMthFromPlans(next),
    investRet,
    planMth,
    planLump,
    planSum,
    planPrem,
  };
}

