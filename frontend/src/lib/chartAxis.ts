/** Axis helpers shared with Scenario Visualizer charts. */

export type AxisMode = 'age' | 'year';

export const DEFAULT_CHART_MAX_AGE = 85;

export function buildXAxis(length: number, startAge: number): number[] {
  return Array.from({ length }, (_, i) => startAge + i);
}

export function defaultRangeEndIndex(
  length: number,
  startAge: number,
  maxAge = DEFAULT_CHART_MAX_AGE,
): number {
  if (length <= 0) return 0;
  const years = Math.max(0, maxAge - startAge);
  return Math.min(length - 1, years);
}

export function floorWealth(series: number[]): number[] {
  return series.map(v => Math.max(0, Number(v) || 0));
}

export type VisibleYRangeOpts = {
  padFrac?: number;
  includeZero?: boolean;
};

export function visibleYRange(
  seriesList: ReadonlyArray<ReadonlyArray<number>>,
  lo: number,
  hi: number,
  opts: VisibleYRangeOpts = {},
): [number, number] | undefined {
  const padFrac = opts.padFrac ?? 0.08;
  let min = Infinity;
  let max = -Infinity;
  const start = Math.max(0, lo);
  for (const series of seriesList) {
    if (!series.length) continue;
    const end = Math.min(hi, series.length - 1);
    for (let i = start; i <= end; i++) {
      const v = Number(series[i]);
      if (!Number.isFinite(v)) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return undefined;
  if (opts.includeZero) {
    min = Math.min(min, 0);
    max = Math.max(max, 0);
  }
  if (min === max) {
    const delta = Math.abs(min) * 0.1 || 1;
    return [min - delta, max + delta];
  }
  const pad = (max - min) * padFrac;
  return [min - pad, max + pad];
}

export function visibleStackedYRange(
  seriesList: ReadonlyArray<ReadonlyArray<number>>,
  lo: number,
  hi: number,
  opts: VisibleYRangeOpts = {},
): [number, number] | undefined {
  const padFrac = opts.padFrac ?? 0.08;
  if (!seriesList.length) return undefined;
  const len = Math.max(...seriesList.map(s => s.length));
  if (len <= 0) return undefined;
  const start = Math.max(0, lo);
  const end = Math.min(hi, len - 1);
  let min = Infinity;
  let max = -Infinity;
  for (let i = start; i <= end; i++) {
    let sum = 0;
    for (const series of seriesList) {
      const v = Number(series[i]);
      if (Number.isFinite(v)) sum += v;
    }
    if (sum < min) min = sum;
    if (sum > max) max = sum;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return undefined;
  if (opts.includeZero) {
    min = Math.min(min, 0);
    max = Math.max(max, 0);
  }
  if (min === max) {
    const delta = Math.abs(min) * 0.1 || 1;
    return [min - delta, max + delta];
  }
  const pad = (max - min) * padFrac;
  return [min - pad, max + pad];
}
