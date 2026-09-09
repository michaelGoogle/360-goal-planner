import { happiBand, HAPPI_COL } from '../lib/types';

export function HappiUGauge({
  value,
  size = 240,
  showBand = true,
}: {
  value: number;
  size?: number;
  showBand?: boolean;
  compact?: boolean;
}) {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  const b = happiBand(v);
  const W = 240;
  const sw = 18;
  const labelPad = 18;
  const R = W / 2 - labelPad - sw / 2;
  const cx = W / 2;
  const cy = labelPad + sw / 2 + R;
  const hubR = R * 0.46;
  const H = Math.ceil(showBand ? cy + R * 0.42 : cy + hubR + 12);
  const pt = (val: number, rad: number) => {
    const a = ((180 - val * 1.8) * Math.PI) / 180;
    return [cx + rad * Math.cos(a), cy - rad * Math.sin(a)] as const;
  };
  const arc = (a1: number, a2: number, rad: number) => {
    const [x1, y1] = pt(a1, rad);
    const [x2, y2] = pt(a2, rad);
    return `M${x1} ${y1} A${rad} ${rad} 0 0 1 ${x2} ${y2}`;
  };
  const ticks = [];
  for (let t = 2; t < 100; t += 2) {
    const [x1, y1] = pt(t, R - sw / 2 + 2);
    const [x2, y2] = pt(t, R + sw / 2 - 2);
    ticks.push(<line key={t} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#fff" strokeWidth="1" opacity=".55" />);
  }
  const labs = [0, 25, 50, 75, 100].map(t => {
    const [x, y] = pt(t, R + sw / 2 + 11);
    return (
      <text key={t} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="11" fontWeight={700} fill="#AEB6C0">
        {t}
      </text>
    );
  });
  const [px, py] = pt(v, R - sw / 2 - 2);
  const [l1x, l1y] = pt(v - 6, hubR * 0.55);
  const [l2x, l2y] = pt(v + 6, hubR * 0.55);
  const id = `xg${v}_${size}_${showBand ? 1 : 0}`;
  return (
    <div className="x-gauge" style={{ maxWidth: size }}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label={`HappiU Score ${v} of 100, ${b.toLowerCase()}`}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#F0876B" />
            <stop offset="28%" stopColor="#F3B24A" />
            <stop offset="58%" stopColor="#EFDD73" />
            <stop offset="100%" stopColor="#7FD69B" />
          </linearGradient>
        </defs>
        <path d={arc(0, 100, R)} fill="none" stroke={`url(#${id})`} strokeWidth={sw} strokeLinecap="round" />
        {ticks}
        <path d={arc(0, 100, R)} fill="none" stroke="#fff" strokeWidth={3} opacity=".5" />
        <polygon points={`${px},${py} ${l1x},${l1y} ${l2x},${l2y}`} fill="#1B2A4A" />
        <circle cx={cx} cy={cy} r={hubR} fill="#fff" />
        <text x={cx} y={cy} textAnchor="middle">
          <tspan x={cx} dy="-0.2em" fontSize="42" fontWeight={800} fill="#111A2B">
            {v}
          </tspan>
          <tspan x={cx} dy="1.35em" fontSize="11" fill="#8B95A2">
            of 100
          </tspan>
        </text>
        {showBand ? (
          <text x={cx} y={cy + R * 0.33} textAnchor="middle" fontSize="12" fontWeight={800} letterSpacing="1" fill={HAPPI_COL[b]}>
            {b}
          </text>
        ) : null}
        {labs}
      </svg>
    </div>
  );
}
