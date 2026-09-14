/** Signed-off workbook defaults from the HTML ASSUME_DEF / Singapore Appendix 4. */
export const ASSUME_DEFAULTS = {
  inflationRate: 0.023,
  interestRate: 0.012,
  incomeGrowthRate: 0.028,
  investmentReturn: 0.042,
  assetReturn: 0.03,
} as const;

export type AssumeKey = keyof typeof ASSUME_DEFAULTS;

/** Plan net-expected-return slider, in percent. After product costs — not headline fund return. */
export const NET_RETURN_PCT_MIN = 2.2;
export const NET_RETURN_PCT_MAX = 10;

/**
 * Green (likely after 2–4% p.a. wrapper / sales costs) → red (10% net is unrealistic).
 * Stops sit at ~2.2%, 4.2% (default), 6%, 7.5%, 10%.
 */
export const NET_RETURN_TRACK_GRADIENT =
  'linear-gradient(90deg, #16a34a 0%, #65a30d 26%, #eab308 49%, #f97316 68%, #dc2626 100%)';

export const NET_RETURN_TIP =
  'Annual growth after product costs — not the headline fund return. Insurance investment plans typically take a sales load (charged up front or at exit) and 2–4% a year in fund and wrapper fees. Net expected return is fund performance minus those costs. Around 4% is a cautious planning rate; 10% after costs is highly unlikely.';

type RGB = [number, number, number];

const NET_RETURN_STOPS: { t: number; rgb: RGB }[] = [
  { t: 0, rgb: [22, 163, 74] },
  { t: 0.26, rgb: [101, 163, 13] },
  { t: 0.49, rgb: [234, 179, 8] },
  { t: 0.68, rgb: [249, 115, 22] },
  { t: 1, rgb: [220, 38, 38] },
];

function lerp(a: number, b: number, t: number) {
  return Math.round(a + (b - a) * t);
}

/** Colour for the net-return readout / thumb at a percent rate (2.2–10). */
export function netExpectedReturnColor(pct: number): string {
  const span = NET_RETURN_PCT_MAX - NET_RETURN_PCT_MIN;
  const t = Math.min(1, Math.max(0, (pct - NET_RETURN_PCT_MIN) / span));
  let i = 0;
  while (i < NET_RETURN_STOPS.length - 2 && t > NET_RETURN_STOPS[i + 1]!.t) i += 1;
  const a = NET_RETURN_STOPS[i]!;
  const b = NET_RETURN_STOPS[i + 1]!;
  const u = (t - a.t) / (b.t - a.t || 1);
  return `rgb(${lerp(a.rgb[0], b.rgb[0], u)}, ${lerp(a.rgb[1], b.rgb[1], u)}, ${lerp(a.rgb[2], b.rgb[2], u)})`;
}

export function pctAn(v: number): string {
  return `${(v * 100).toFixed(2).replace(/\.?0+$/, '')}% p.a.`;
}

export function assumeChangedCount(s: Record<AssumeKey, number>): number {
  return (Object.keys(ASSUME_DEFAULTS) as AssumeKey[]).reduce((n, k) => {
    return n + (Math.round(s[k] * 1000) !== Math.round(ASSUME_DEFAULTS[k] * 1000) ? 1 : 0);
  }, 0);
}

/** Plan net-expected-return slider is percent (4.2); session investmentReturn is a fraction (0.042). */
export function investRetFromReturn(investmentReturn: number): number {
  return Math.min(
    NET_RETURN_PCT_MAX,
    Math.max(NET_RETURN_PCT_MIN, Math.round(investmentReturn * 1000) / 10),
  );
}

export function returnFromInvestRet(investRet: number): number {
  return Math.min(NET_RETURN_PCT_MAX / 100, Math.max(NET_RETURN_PCT_MIN / 100, Math.round(investRet * 10) / 1000));
}
