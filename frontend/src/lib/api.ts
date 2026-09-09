import { parseSentence, type ParsedSentence } from './parse';
import type { SvData } from './sv';
import type { GpSession, NeedRow } from './types';

export async function postJson<T>(
  path: string,
  body: unknown,
  token?: string | null,
  signal?: AbortSignal,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { method: 'POST', headers, body: JSON.stringify(body), signal });
  const data = (await res.json()) as T & { detail?: unknown };
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data);
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return data;
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { method: 'GET', signal });
  const data = (await res.json()) as T & { detail?: unknown };
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data);
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return data;
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
    const llmError = err instanceof Error && err.message ? err.message : 'AI could not read that sentence.';
    if (opts?.regexFallback === false) return { fields: {}, ai: false, llmError };
    return { fields: parseSentence(text), ai: false, llmError };
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
    events: s.events,
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
}
