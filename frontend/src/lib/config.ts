/**
 * The config service, as the UI sees it.
 *
 * Values, bounds and which version is active all come from the backend
 * (`config/parameters/v24.json`), so a published parameter change reaches the UI
 * without a rebuild. Copy stays here: the workbook names a parameter
 * `inflationRate`, the assumption box calls it "Price inflation".
 *
 * `ASSUME_FALLBACK` is used only while the first fetch is in flight, or if the
 * backend is unreachable, so the modal is never blank.
 */

import { getJson, putJson } from './api';

export type ParameterLevel = 'admin' | 'customer';

export interface Parameter {
  name: string;
  value: number | string | boolean;
  unit: string;
  currency: string;
  level: ParameterLevel;
  label: string;
  codeSource: string;
  changedIn: string;
  min?: number | null;
  max?: number | null;
}

export interface ParameterSet {
  version: string;
  model: string;
  createdAt: string;
  createdBy: string;
  note: string;
  parameters: Record<string, Parameter>;
}

export interface AssumptionSchema {
  version: string;
  fields: Parameter[];
}

export interface AuditEntry {
  version: string;
  createdAt: string;
  createdBy: string;
  note: string;
  diff: Record<string, { from?: unknown; to?: unknown }>;
}

export const ASSUME_KEYS = [
  'inflationRate',
  'interestRate',
  'loanRate',
  'incomeGrowthRate',
  'investmentReturn',
  'assetReturn',
] as const;

export type AssumeKey = (typeof ASSUME_KEYS)[number];

export const ASSUME_FALLBACK: Record<AssumeKey, number> = {
  inflationRate: 0.023,
  interestRate: 0.012,
  loanRate: 0.035,
  incomeGrowthRate: 0.028,
  investmentReturn: 0.042,
  assetReturn: 0.03,
};

export interface AssumeBound {
  value: number;
  min?: number;
  max?: number;
}

/** What the assumption box needs: a default and the range an edit must stay inside. */
export type AssumeConfig = Record<AssumeKey, AssumeBound>;

export const ASSUME_CONFIG_FALLBACK: AssumeConfig = Object.fromEntries(
  ASSUME_KEYS.map(k => [k, { value: ASSUME_FALLBACK[k] }]),
) as AssumeConfig;

function numeric(p: Parameter): number | null {
  return typeof p.value === 'number' ? p.value : null;
}

export function assumeConfigFrom(schema: AssumptionSchema | null): AssumeConfig {
  if (!schema) return ASSUME_CONFIG_FALLBACK;
  const byName = new Map(schema.fields.map(f => [f.name, f]));
  return Object.fromEntries(
    ASSUME_KEYS.map(k => {
      const field = byName.get(k);
      const value = field ? numeric(field) : null;
      if (!field || value === null) return [k, { value: ASSUME_FALLBACK[k] }];
      return [
        k,
        {
          value,
          min: field.min ?? undefined,
          max: field.max ?? undefined,
        },
      ];
    }),
  ) as AssumeConfig;
}

export function assumeDefaults(config: AssumeConfig): Record<AssumeKey, number> {
  return Object.fromEntries(ASSUME_KEYS.map(k => [k, config[k].value])) as Record<AssumeKey, number>;
}

/** How many rates the customer has moved away from the published default. */
export function assumeChangedCount(
  session: Partial<Record<AssumeKey, number | null | undefined>>,
  config: AssumeConfig,
): number {
  return ASSUME_KEYS.reduce((n, k) => {
    const v = session[k];
    if (v === null || v === undefined) return n;
    return n + (Math.round(v * 1000) !== Math.round(config[k].value * 1000) ? 1 : 0);
  }, 0);
}

let schemaCache: Promise<AssumptionSchema> | null = null;

export function fetchAssumptionSchema(): Promise<AssumptionSchema> {
  schemaCache ??= getJson<AssumptionSchema>('/v1/config/session-assumptions/schema');
  return schemaCache;
}

export function fetchParameters(version?: string): Promise<ParameterSet> {
  return getJson<ParameterSet>(
    version ? `/v1/config/parameters/${version}` : '/v1/config/parameters',
  );
}

export function fetchVersions(): Promise<string[]> {
  return getJson<string[]>('/v1/config/versions');
}

export interface SessionDefaults {
  age: number;
  country: string;
  ageOfRetirement: number;
  lifeExpectancy: number;
  ltcStartAge: number;
  targetYear: Record<string, number>;
  parametersVersion: string;
}

export function fetchSessionDefaults(age: number, country = 'Singapore'): Promise<SessionDefaults> {
  const q = new URLSearchParams({ age: String(age), country });
  return getJson<SessionDefaults>(`/v1/config/session-defaults?${q}`);
}

export function fetchAudit(): Promise<AuditEntry[]> {
  return getJson<AuditEntry[]>('/v1/config/audit');
}

/** Saves a new version. The active version is never edited in place. */
export function putParameters(
  parameters: Record<string, number | string>,
  note: string,
  token: string | null,
  basedOn?: string,
): Promise<ParameterSet> {
  schemaCache = null;
  return putJson<ParameterSet>(
    '/v1/config/parameters',
    { parameters, note, basedOn: basedOn ?? '' },
    token,
  );
}
