import { type ReactNode } from 'react';
import { Ico } from '../lib/icons';
import { pctAn } from '../lib/assumptions';
import { firstName, money, type GpSession, type Prov } from '../lib/types';

export function SecHead({
  n,
  title,
  sub,
  onToggle,
  open,
  badge,
}: {
  n: number;
  title: string;
  sub?: string;
  onToggle?: () => void;
  open?: boolean;
  badge?: ReactNode;
}) {
  const inner = (
    <>
      <span className="n">{n}</span>
      <span className="t">
        <b>{title}</b>
        {sub ? <span>{sub}</span> : null}
      </span>
      {badge}
      {onToggle ? <span className="cv">{Ico.chev}</span> : null}
    </>
  );
  if (onToggle) {
    return (
      <button className="x-sech" type="button" onClick={onToggle} aria-expanded={!!open}>
        {inner}
      </button>
    );
  }
  return <div className="x-sech st">{inner}</div>;
}

export function ClassicToggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      className={`x-tog ${on ? 'on' : ''}`}
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onClick}
      title={on ? 'Back to one sentence' : 'Fill the form yourself instead'}
    >
      <span className="x-togl">Enter data classically</span>
      <span className="x-togs">
        <i className="x-togk" />
      </span>
    </button>
  );
}

export function Tip({
  id,
  open,
  onToggle,
  edit,
  right,
  wide,
  children,
}: {
  id: string;
  open: string | null;
  onToggle: (id: string) => void;
  edit?: boolean;
  right?: boolean;
  wide?: boolean;
  children: ReactNode;
}) {
  const on = open === id;
  return (
    <span className="x-tipw">
      <button
        className={`x-tipb ${edit ? 'ed' : ''} ${on ? 'on' : ''}`}
        type="button"
        aria-expanded={on}
        aria-label={edit ? 'Change this figure' : 'Why this figure'}
        onClick={() => onToggle(id)}
      >
        {edit ? Ico.pencil : Ico.info}
      </button>
      {on ? (
        <span className={`x-tip ${right ? 'r' : ''} ${wide ? 'w' : ''}`} role="dialog">
          <button className="cl" type="button" aria-label="Close" onClick={() => onToggle(id)}>
            {Ico.close}
          </button>
          {children}
        </span>
      ) : null}
    </span>
  );
}

export function GroupTag({
  session,
  keys,
  verb,
}: {
  session: GpSession;
  keys: string[];
  verb: string;
}) {
  const vals = keys.map(k => session.provenance[k]).filter(Boolean) as Prov[];
  if (vals.includes('doc')) {
    return (
      <em className="x-gtag doc">
        {Ico.check}Read from your documents
      </em>
    );
  }
  if (vals.includes('you')) {
    return (
      <em className="x-gtag you">
        {Ico.check}Your own figures
      </em>
    );
  }
  const nm = firstName(session);
  return (
    <em className="x-gtag">
      {Ico.wand}
      People like {nm === 'you' ? 'you' : nm} {verb}
    </em>
  );
}

const PIE_FILL: Record<string, string> = {
  pos: '#2563EB',
  pos2: '#6E93F2',
  neg: '#E5484D',
  tot: '#12A150',
};

export type EqSlice = {
  l: string;
  v: number;
  c?: 'pos' | 'pos2' | 'neg' | 'tot';
  fill?: string;
  op?: string;
};

function piePoint(cx: number, cy: number, r: number, angle: number): [number, number] {
  const rad = ((angle - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

function donutSlice(cx: number, cy: number, rOut: number, rIn: number, a0: number, a1: number): string {
  const span = a1 - a0;
  if (span >= 359.99) {
    const [o0, o1] = [piePoint(cx, cy, rOut, 0), piePoint(cx, cy, rOut, 180)];
    const [i0, i1] = [piePoint(cx, cy, rIn, 180), piePoint(cx, cy, rIn, 0)];
    return [
      `M ${o0[0]} ${o0[1]}`,
      `A ${rOut} ${rOut} 0 1 1 ${o1[0]} ${o1[1]}`,
      `A ${rOut} ${rOut} 0 1 1 ${o0[0]} ${o0[1]}`,
      `L ${i1[0]} ${i1[1]}`,
      `A ${rIn} ${rIn} 0 1 0 ${i0[0]} ${i0[1]}`,
      `A ${rIn} ${rIn} 0 1 0 ${i1[0]} ${i1[1]}`,
      'Z',
    ].join(' ');
  }
  const large = span > 180 ? 1 : 0;
  const [x0, y0] = piePoint(cx, cy, rOut, a0);
  const [x1, y1] = piePoint(cx, cy, rOut, a1);
  const [xi1, yi1] = piePoint(cx, cy, rIn, a1);
  const [xi0, yi0] = piePoint(cx, cy, rIn, a0);
  return `M ${x0} ${y0} A ${rOut} ${rOut} 0 ${large} 1 ${x1} ${y1} L ${xi1} ${yi1} A ${rIn} ${rIn} 0 ${large} 0 ${xi0} ${yi0} Z`;
}

export function EqPie({
  rows,
}: {
  rows: EqSlice[];
}) {
  const parts = rows.filter(r => Math.abs(r.v) > 0);
  const total = parts.reduce((s, r) => s + Math.abs(r.v), 0);
  const gap = parts.length > 1 ? 3.2 : 0;
  let angle = 0;
  const slices =
    total > 0
      ? parts.map(r => {
          const span = (Math.abs(r.v) / total) * 360;
          const a0 = angle + gap / 2;
          const a1 = angle + span - gap / 2;
          angle += span;
          return { ...r, d: a1 > a0 ? donutSlice(50, 50, 42, 26, a0, a1) : '' };
        })
      : [];
  return (
    <div className="chart">
      <div className="x-pie">
        <div className="x-pied">
          <svg viewBox="0 0 100 100" aria-hidden>
            {slices.map((s, i) =>
              s.d ? (
                <path key={`${s.l}-${i}`} d={s.d} fill={s.fill || PIE_FILL[s.c || 'pos']} />
              ) : null,
            )}
            {!slices.length ? <circle cx="50" cy="50" r="42" fill="none" stroke="#EEF1F5" strokeWidth="16" /> : null}
          </svg>
        </div>
        <div className="x-gkey">
          {rows.map((r, i) => (
            <span className="x-gi" key={`${r.l}-${i}`}>
              {r.op ? <em className="x-gop">{r.op}</em> : null}
              <span className={`x-gk ${r.c || ''}`}>
                <i style={r.fill ? { background: r.fill } : undefined} />
                <span className="l">
                  {r.l} <b>({money(Math.abs(r.v))})</b>
                </span>
              </span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export function NarrBtn({
  label,
  ariaLabel,
  on,
  paused,
  onClick,
}: {
  label: ReactNode;
  ariaLabel?: string;
  on?: boolean;
  paused?: boolean;
  onClick: () => void;
}) {
  const playing = !!on && !paused;
  return (
    <button
      className={`x-play ${on ? 'on' : ''}${paused ? ' paused' : ''}`}
      type="button"
      onClick={onClick}
      aria-pressed={!!on}
      aria-label={ariaLabel ?? (typeof label === 'string' ? label : undefined)}
    >
      {playing ? Ico.pause : Ico.play}
      {label}
    </button>
  );
}

export function Foot({ children }: { children: ReactNode }) {
  return (
    <div className="x-sticky">
      <div className="x-foot" style={{ margin: 0 }}>
        {children}
      </div>
    </div>
  );
}

export function Switch({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  return (
    <button className={`tgl ${on ? 'on' : ''}`} type="button" role="switch" aria-checked={on} aria-label={label} onClick={onClick} />
  );
}

export function RateSlider({
  label,
  min,
  max,
  step,
  value,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="gsl">
      <div className="gsl-h">
        <label>{label}</label>
        <b>{pctAn(value)}</b>
      </div>
      <input
        type="range"
        className="objrange"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={label}
        onChange={e => onChange(Number(e.target.value))}
      />
    </div>
  );
}
