import { sessionCountry, sessionCurrency } from './currency';
import type { ParsedSentence } from './parse';
import { hydrateStressEvents } from './stressEvents';
import type { SvData } from './sv';
import { takeHomeMonthly, type GpSession, type NeedRow } from './types';

function plannerUnreachable(message: string): boolean {
  return /^(HTTP 502|HTTP 504)\b/.test(message) || message === 'HTTP 503' || /failed to fetch|networkerror|load failed/i.test(message);
}

function llmCatchMessage(err: unknown): string {
  const msg = err instanceof Error && err.message ? err.message : 'AI could not read that sentence.';
  if (plannerUnreachable(msg)) return 'The planning service is not running.';
  return msg;
}

async function readJson<T>(res: Response): Promise<T & { detail?: unknown }> {
  const raw = await res.text();
  if (!raw.trim()) throw new Error(`HTTP ${res.status}`);
  try {
    return JSON.parse(raw) as T & { detail?: unknown };
  } catch {
    throw new Error(`HTTP ${res.status}`);
  }
}

function throwIfNotOk<T>(res: Response, data: T & { detail?: unknown }): T {
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data);
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return data;
}

export async function postJson<T>(
  path: string,
  body: unknown,
  token?: string | null,
  signal?: AbortSignal,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { method: 'POST', headers, body: JSON.stringify(body), signal });
  return throwIfNotOk(res, await readJson<T>(res));
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { method: 'GET', signal });
  return throwIfNotOk(res, await readJson<T>(res));
}

export async function putJson<T>(path: string, body: unknown, token?: string | null): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { method: 'PUT', headers, body: JSON.stringify(body) });
  return throwIfNotOk(res, await readJson<T>(res));
}

export interface ParseSentenceResponse {
  success: boolean;
  source: string;
  fields: ParsedSentence;
}

export async function parseAboutYou(
  text: string,
  signal?: AbortSignal,
  opts?: { regexFallback?: boolean },
): Promise<{ fields: ParsedSentence; ai: boolean; llmError?: string }> {
  const fallback = async () => (await import('./parse')).parseSentence(text);
  try {
    const data = await postJson<ParseSentenceResponse>('/v1/parse-sentence', { text }, null, signal);
    if (data.source === 'llm') return { fields: data.fields || {}, ai: true };
    if (data.source === 'unavailable') {
      const fields = opts?.regexFallback === false ? {} : await fallback();
      return { fields, ai: false, llmError: 'AI is not configured on this server (ANTHROPIC_API_KEY).' };
    }
  } catch (err) {
    if (signal?.aborted || (err instanceof Error && err.name === 'AbortError')) throw err;
    const llmError = llmCatchMessage(err);
    if (opts?.regexFallback === false) return { fields: {}, ai: false, llmError };
    const fields = await fallback();
    if (Object.keys(fields).length && plannerUnreachable(err instanceof Error ? err.message : '')) {
      return { fields, ai: false };
    }
    return { fields, ai: false, llmError };
  }
  return { fields: await fallback(), ai: false };
}

export interface PlanNeedResult {
  type: string;
  suggested: boolean;
  included: boolean;
  planSum: number;
  planPrem: number;
  planMth: number;
  planLump: number;
  capMth: number;
  fv: number;
  remain: number;
}

export interface PlanResponse {
  needs: PlanNeedResult[];
  investMth: number;
  investLump: number;
  protPremYear: number;
  currency: string;
}

export interface BudgetResponse {
  available: number;
  free: number;
  monthly: number;
  monthlyOver: number;
  lumps: number;
  lumpOver: number;
  currency: string;
}

export interface FxLock {
  currency: string;
  country: string;
  usdPerLocal: number;
  priceLevel: number;
  asOf: string;
  source: string;
}

export async function postPlan(session: GpSession, token?: string | null): Promise<PlanResponse> {
  return postJson<PlanResponse>(
    '/v1/plan',
    {
      age: typeof session.age === 'number' ? session.age : 40,
      gender: session.gender || 'Male',
      smoker: !!session.isSmoker,
      country: sessionCountry(session),
      currency: sessionCurrency(session),
      takeHomeMonthly: takeHomeMonthly(session),
      expenseMonthly: session.expenseMonthly || 0,
      ageOfRetirement: session.ageOfRetirement || 65,
      inflationRate: session.inflationRate,
      investmentReturn: session.investmentReturn,
      plansOff: session.plansOff || [],
      parametersVersion: session.parametersVersion || '',
      needs: (session.needs || []).map(n => ({
        type: n.type,
        enabled: !!n.enabled,
        needAmount: n.needAmount || 0,
        have: n.have || 0,
        gap: n.gap ?? Math.max(0, (n.needAmount || 0) - (n.have || 0)),
        horizonYears: n.contributeYears,
        touchedSum: !!session.planSumTouched?.[n.type],
        touchedMth: !!session.planMthTouched?.[n.type],
        touchedLump: !!session.planLumpTouched?.[n.type],
        planSum: session.planSum?.[n.type],
        planMth: session.planMth?.[n.type],
        planLump: session.planLump?.[n.type],
      })),
    },
    token,
  );
}

export async function postBudget(session: GpSession, token?: string | null): Promise<BudgetResponse> {
  const includedPremiumsYear = (session.needs || [])
    .filter(n => n.enabled && !(session.plansOff || []).includes(n.type))
    .reduce((sum, n) => sum + (session.planPrem?.[n.type] || 0), 0);
  return postJson<BudgetResponse>(
    '/v1/budget',
    {
      takeHomeMonthly: takeHomeMonthly(session),
      expenseMonthly: session.expenseMonthly || 0,
      investments: session.investments || 0,
      includedPremiumsYear,
      investMth: session.investMth || 0,
      investLump: session.investLump || 0,
      currency: sessionCurrency(session),
      parametersVersion: session.parametersVersion || '',
    },
    token,
  );
}

export async function lockFx(currency: string, country: string): Promise<FxLock> {
  return postJson<FxLock>('/v1/fx/lock', { currency, country });
}

export function sessionPayload(s: GpSession) {
  return {
    name: s.name,
    age: typeof s.age === 'number' ? s.age : 40,
    gender: s.gender,
    country: sessionCountry(s),
    currency: sessionCurrency(s),
    fx: s.fx,
    residency: s.residency,
    nationality: s.nationality,
    occupation: s.occupation,
    dependents: s.dependents,
    dateOfBirth: s.dateOfBirth || (typeof s.age === 'number' ? `${new Date().getFullYear() - s.age}-01-01` : undefined),
    isSmoker: s.isSmoker,
    riskProfile: s.riskProfile,
    ageOfRetirement: s.ageOfRetirement,
    incomeMonthly: s.incomeMonthly,
    expenseMonthly: s.expenseMonthly,
    cash: s.cash,
    investments: s.investments,
    property: s.property,
    mortgage: s.mortgage,
    policies: s.policies,
    needs: s.needs,
    events: hydrateStressEvents(s.events),
    plansOff: s.plansOff,
    planMth: s.planMth,
    planLump: s.planLump,
    planSum: s.planSum,
    planPrem: s.planPrem,
    extraNeeds: s.extraNeeds,
    cpfOa: s.cpfOa,
    cpfSa: s.cpfSa,
    cpfMa: s.cpfMa,
    reportEmail: s.reportEmail || '',
    reportMobile: s.reportMobile || '',
    insapiContactId: s.insapiContactId || '',
    insapiPlanId: s.insapiPlanId || '',
    inflationRate: s.inflationRate,
    interestRate: s.interestRate,
    loanRate: s.loanRate,
    incomeGrowthRate: s.incomeGrowthRate,
    investmentReturn: s.investmentReturn,
    assetReturn: s.assetReturn,
    parametersVersion: s.parametersVersion || '',
    lifeExpectancy: s.lifeExpectancy ?? undefined,
  };
}

export interface PredictResponse {
  success: boolean;
  notes: string[];
  session: Partial<GpSession> & { needs?: NeedRow[]; note?: string; source?: string };
}

export interface NeedsResponse {
  success: boolean;
  session: { needs: NeedRow[]; ageOfRetirement?: number };
}

export interface CrmSyncResponse {
  success: boolean;
  contactId?: string;
  planId?: string;
}

export interface ScoreResponse {
  success: boolean;
  preHappiU: number | null;
  postHappiU: number | null;
  result: Record<string, unknown> | null;
  breakdown: unknown;
}

export interface ProjectResponse {
  success: boolean;
  data: SvData | null;
  payload?: Record<string, unknown> | null;
}
