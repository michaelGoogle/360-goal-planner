/** Dual-thumb range slider — same control as Scenario Visualizer. */

import { PLOT_MARGIN } from './Plot';

interface Props {
  min: number;
  max: number;
  value: [number, number];
  labels: number[];
  axisLabel: string;
  onChange: (next: [number, number]) => void;
}

export function RangeSlider({ min, max, value, labels, axisLabel, onChange }: Props) {
  const [lo, hi] = value;
  const span = Math.max(1, max - min);

  function setLo(raw: number) {
    const next = Math.min(Math.max(min, raw), hi);
    onChange([next, hi]);
  }

  function setHi(raw: number) {
    const next = Math.max(Math.min(max, raw), lo);
    onChange([lo, next]);
  }

  const loPct = ((lo - min) / span) * 100;
  const hiPct = ((hi - min) / span) * 100;
  const loLabel = labels[lo] ?? lo;
  const hiLabel = labels[hi] ?? hi;

  return (
    <div
      className="pb-3 pt-0 select-none"
      style={{ paddingLeft: PLOT_MARGIN.l, paddingRight: PLOT_MARGIN.r }}
    >
      <div className="relative h-8 flex items-center">
        <div className="absolute left-0 right-0 h-2 rounded-full bg-[#d0d7e8]" />
        <div
          className="absolute h-2 rounded-full bg-[#3B5BDB]"
          style={{ left: `${loPct}%`, width: `${Math.max(0, hiPct - loPct)}%` }}
        />
        <input
          type="range"
          aria-label={`${axisLabel} start`}
          min={min}
          max={max}
          value={lo}
          onChange={e => setLo(Number(e.target.value))}
          className="sv-range-thumb absolute inset-0 w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-moz-range-thumb]:pointer-events-auto"
        />
        <input
          type="range"
          aria-label={`${axisLabel} end`}
          min={min}
          max={max}
          value={hi}
          onChange={e => setHi(Number(e.target.value))}
          className="sv-range-thumb absolute inset-0 w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-moz-range-thumb]:pointer-events-auto"
        />
      </div>
      <div className="flex justify-between text-sm text-[#666] mt-0.5 tabular-nums">
        <span>
          {axisLabel} {loLabel}
        </span>
        <span>
          {axisLabel} {hiLabel}
        </span>
      </div>
    </div>
  );
}
