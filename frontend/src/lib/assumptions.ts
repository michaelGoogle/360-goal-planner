/** Signed-off workbook defaults from the HTML ASSUME_DEF / Singapore Appendix 4. */
export const ASSUME_DEFAULTS = {
  inflationRate: 0.023,
  interestRate: 0.012,
  incomeGrowthRate: 0.028,
  investmentReturn: 0.042,
  assetReturn: 0.03,
} as const;

export type AssumeKey = keyof typeof ASSUME_DEFAULTS;

export function pctAn(v: number): string {
  return `${(v * 100).toFixed(2).replace(/\.?0+$/, '')}% p.a.`;
}

export function assumeChangedCount(s: Record<AssumeKey, number>): number {
  return (Object.keys(ASSUME_DEFAULTS) as AssumeKey[]).reduce((n, k) => {
    return n + (Math.round(s[k] * 1000) !== Math.round(ASSUME_DEFAULTS[k] * 1000) ? 1 : 0);
  }, 0);
}
