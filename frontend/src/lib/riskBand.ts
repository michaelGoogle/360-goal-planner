/**
 * Same 1–5 names and annual-vol brackets as PA / portal
 * (`PA/frontend/src/lib/riskBand.ts`, `portal/src/lib/riskBand.ts`).
 * Chip classes are restyled for the light Score card.
 */

export type RiskBand = 'Low' | 'Low-Medium' | 'Medium' | 'Medium-High' | 'High';

export type RiskProfile = 1 | 2 | 3 | 4 | 5;

export interface RiskLevel {
  profile: RiskProfile;
  label: RiskBand;
  volLabel: string;
  /** Light-theme chip modifier: `x-chip r1` … `r5`. */
  chipClass: string;
  track: string;
  accent: string;
}

export const RISK_LEVELS: readonly RiskLevel[] = [
  {
    profile: 1,
    label: 'Low',
    volLabel: '< 10%',
    chipClass: 'r1',
    track: '#10b981',
    accent: '#059669',
  },
  {
    profile: 2,
    label: 'Low-Medium',
    volLabel: '10% – 15%',
    chipClass: 'r2',
    track: '#84cc16',
    accent: '#65a30d',
  },
  {
    profile: 3,
    label: 'Medium',
    volLabel: '15% – 20%',
    chipClass: 'r3',
    track: '#f59e0b',
    accent: '#d97706',
  },
  {
    profile: 4,
    label: 'Medium-High',
    volLabel: '20% – 30%',
    chipClass: 'r4',
    track: '#f97316',
    accent: '#ea580c',
  },
  {
    profile: 5,
    label: 'High',
    volLabel: '≥ 30%',
    chipClass: 'r5',
    track: '#f43f5e',
    accent: '#e11d48',
  },
];

export const RISK_TRACK_GRADIENT =
  'linear-gradient(90deg, #10b981 0%, #84cc16 25%, #f59e0b 50%, #f97316 75%, #f43f5e 100%)';

export function clampRiskProfile(n: number | null | undefined): RiskProfile {
  const r = Math.round(Number(n));
  if (!Number.isFinite(r)) return 3;
  return Math.min(5, Math.max(1, r)) as RiskProfile;
}

export function riskLevel(profile: number): RiskLevel {
  return RISK_LEVELS[clampRiskProfile(profile) - 1]!;
}
