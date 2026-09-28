/**
 * Need and risk codes, from docs/calculations/Need-dictionary.md.
 *
 * The TypeScript half of src/needs.py. Both list the same codes, and the parity test
 * in tests/test_need_codes.py fails if they drift.
 *
 * Old ids are accepted on input for one release: a session lives in the browser and in
 * InsApi, not in a database we could migrate.
 */

export type CalculatorNeed =
  | 'N_INC'
  | 'N_CRI'
  | 'N_TPD'
  | 'N_HOS'
  | 'N_PAC'
  | 'N_LTC'
  | 'N_RET'
  | 'N_EDU'
  | 'N_SAV'
  | 'N_PRP';

/** Coverage the profiler ranks but does not size. Nothing to calculate. */
export type ParkedNeed = 'N_HOM' | 'N_CAR' | 'N_TRV';

export const CALCULATOR_NEEDS: CalculatorNeed[] = [
  'N_INC',
  'N_CRI',
  'N_TPD',
  'N_HOS',
  'N_PAC',
  'N_LTC',
  'N_RET',
  'N_EDU',
  'N_SAV',
  'N_PRP',
];

export const PARKED_NEEDS: ParkedNeed[] = ['N_HOM', 'N_CAR', 'N_TRV'];

export const PARKED_NEED_LABEL: Record<ParkedNeed, string> = {
  N_HOM: 'Home protection',
  N_CAR: 'Car protection',
  N_TRV: 'Travel protection',
};

export const NEED_ALIAS: Record<string, CalculatorNeed> = {
  N_HSP: 'N_HOS',
  N_PTD: 'N_TPD',
};

export function needCode(value: unknown): string {
  const code = typeof value === 'string' ? value.trim() : '';
  return NEED_ALIAS[code] ?? code;
}

// --- risks and stress events -------------------------------------------------

export type RiskCode =
  | 'R_MKT'
  | 'R_CCY'
  | 'R_INF'
  | 'R_ICT'
  | 'R_EXP'
  | 'R_DEA'
  | 'R_CRI'
  | 'R_TPD'
  | 'R_PAC'
  | 'R_HOS'
  | 'R_LTC'
  | 'R_WED'
  | 'R_BAB'
  | 'R_LON';

/** The risk each need answers. A savings goal has no trigger. */
export const NEED_RISK: Partial<Record<CalculatorNeed, RiskCode>> = {
  N_INC: 'R_DEA',
  N_CRI: 'R_CRI',
  N_TPD: 'R_TPD',
  N_HOS: 'R_HOS',
  N_PAC: 'R_PAC',
  N_LTC: 'R_LTC',
  N_RET: 'R_LON',
};

export const RISK_ALIAS: Record<string, RiskCode> = {
  crash: 'R_MKT',
  Crash: 'R_MKT',
  MarketCrash: 'R_MKT',
  ccy: 'R_CCY',
  CurrencyShock: 'R_CCY',
  infl: 'R_INF',
  Inflation: 'R_INF',
  inc: 'R_ICT',
  Unemployment: 'R_ICT',
  Income: 'R_ICT',
  exp: 'R_EXP',
  death: 'R_DEA',
  Death: 'R_DEA',
  ci: 'R_CRI',
  CI: 'R_CRI',
  tpd: 'R_TPD',
  ptd: 'R_TPD',
  PTD: 'R_TPD',
  Disability: 'R_TPD',
  pa: 'R_PAC',
  PersonalAccident: 'R_PAC',
  hosp: 'R_HOS',
  Hospitalization: 'R_HOS',
  care: 'R_LTC',
  wed: 'R_WED',
  Marriage: 'R_WED',
  baby: 'R_BAB',
  Newborn: 'R_BAB',
  lon: 'R_LON',
};

export function riskCode(value: unknown): string {
  const code = typeof value === 'string' ? value.trim() : '';
  return RISK_ALIAS[code] ?? code;
}
