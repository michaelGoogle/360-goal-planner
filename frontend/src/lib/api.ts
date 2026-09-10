import { parseSentence, type ParsedSentence } from './parse';
import { hydrateStressEvents } from './stressEvents';
import type { SvData } from './sv';
import type { GpSession, NeedRow } from './types';

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
  try {
    const data = await postJson<ParseSentenceResponse>('/v1/parse-sentence', { text }, null, signal);
    if (data.source === 'llm') return { fields: data.fields || {}, ai: true };
    if (data.source === 'unavailable') {
      const fields = opts?.regexFallback === false ? {} : parseSentence(text);
      return { fields, ai: false, llmError: 'AI is not configured on this server (ANTHROPIC_API_KEY).' };
    }
  } catch (err) {
    if (signal?.aborted || (err instanceof Error && err.name === 'AbortError')) throw err;
    const llmError = llmCatchMessage(err);
    if (opts?.regexFallback === false) return { fields: {}, ai: false, llmError };
    const fields = parseSentence(text);
    if (Object.keys(fields).length && plannerUnreachable(err instanceof Error ? err.message : '')) {
      return { fields, ai: false };
    }
    return { fields, ai: false, llmError };
  }
  return { fields: parseSentence(text), ai: false };
}

export function sessionPayload(s: GpSession) {
  return {
    name: s.name,
    age: typeof s.age === 'number' ? s.age : 40,
    gender: s.gender,
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
    inflationRate: s.inflationRate,
    interestRate: s.interestRate,
    incomeGrowthRate: s.incomeGrowthRate,
    investmentReturn: s.investmentReturn,
    assetReturn: s.assetReturn,
  };
}

export interface PredictResponse {
  success: boolean;
  notes: string[];
  session: Partial<GpSession> & { needs?: NeedRow[]; note?: string; source?: string };
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
