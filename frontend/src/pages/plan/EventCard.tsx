import { useEffect, useState } from 'react';
import { Switch } from '../../components/ui';
import { Ico, ObjIcon } from '../../lib/icons';
import {
  STRESS_BY_ID,
  eventAge,
  formatEventValue,
  isFracValue,
  type GpEvent,
} from '../../lib/stressEvents';
import { AmountSlider } from './CoverCard';

function YearRangeSlider({
  label,
  min,
  max,
  from,
  to,
  format,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  from: number;
  to: number;
  format: (offset: number) => string;
  onChange: (from: number, to: number) => void;
}) {
  const lo = Math.min(from, to);
  const hi = Math.max(from, to);
  const span = Math.max(1, max - min);
  const pc = (v: number) => ((v - min) / span) * 100;
  return (
    <div className="gsl gsl-rng">
      <div className="gsl-h">
        <label>{label}</label>
        <b>
          {format(lo)} – {format(hi)}
        </b>
      </div>
      <div className="gsl-tr">
        <div className="gsl-rail" />
        <div className="gsl-fill" style={{ left: `${pc(lo)}%`, width: `${Math.max(0, pc(hi) - pc(lo))}%` }} />
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={lo}
          aria-label={`${label} start`}
          onChange={e => {
            const v = Number(e.target.value);
            onChange(Math.min(v, hi), hi);
          }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={hi}
          aria-label={`${label} end`}
          onChange={e => {
            const v = Number(e.target.value);
            onChange(lo, Math.max(v, lo));
          }}
        />
      </div>
    </div>
  );
}

export function EventCard({
  ev,
  startAge,
  last,
  startYear,
  startOpen,
  onToggle,
  onPatch,
}: {
  ev: GpEvent;
  startAge: number;
  last: number;
  startYear: number;
  startOpen?: boolean;
  onToggle: () => void;
  onPatch: (p: Partial<GpEvent>) => void;
}) {
  const spec = STRESS_BY_ID[ev.id];
  const [open, setOpen] = useState(!!(ev.on && (startOpen || ev.on)));
  useEffect(() => {
    if (ev.on) setOpen(true);
    else setOpen(false);
  }, [ev.on]);

  if (!spec) return null;
  const rng = spec.kind !== 'one';
  const frac = isFracValue(ev.v);
  const ageOf = (offset: number) => eventAge(startAge, offset, last);
  const yearOf = (offset: number) => startYear + Math.max(0, Math.min(last, offset));
  const when = rng
    ? `Age ${ageOf(ev.from)}–${ageOf(ev.to)} · ${yearOf(ev.from)}`
    : `Age ${ageOf(ev.year)} · ${yearOf(ev.year)}`;
  const val = formatEventValue(ev.v);
  const meta = rng ? `Age ${ageOf(ev.from)}–${ageOf(ev.to)} · ${val}` : `Age ${ageOf(ev.year)} · ${val}`;
  const shown = ev.on && open;
  const color = ev.on ? spec.color : '#CDD2D8';

  return (
    <div className={`gc ${ev.on ? 'on' : ''}${shown ? ' open' : ''}`}>
      <div className="gc-h">
        <button
          className="gc-exp"
          type="button"
          aria-expanded={shown}
          aria-label={shown ? `Collapse ${spec.label}` : `Adjust ${spec.label}`}
          onClick={() => {
            if (!ev.on) onToggle();
            else setOpen(o => !o);
          }}
        >
          <span className="gc-ic" style={{ background: color, color: '#fff', borderColor: color, borderRadius: 8 }}>
            <ObjIcon name={spec.icon} size={14} />
          </span>
          <b>{spec.label}</b>
        </button>
        {ev.on && !shown ? <span className="gc-by">{meta}</span> : null}
        {ev.on ? (
          <button
            className="gc-x"
            type="button"
            title={shown ? 'Done' : 'Adjust'}
            aria-label={shown ? `Collapse ${spec.label}` : `Adjust ${spec.label}`}
            aria-expanded={shown}
            onClick={() => setOpen(o => !o)}
          >
            {shown ? Ico.chev : Ico.pencil}
          </button>
        ) : null}
        <Switch
          on={ev.on}
          label={spec.label}
          onClick={() => {
            if (!ev.on) setOpen(true);
            onToggle();
          }}
        />
      </div>
      {shown ? (
        <div className="gc-e">
          {rng ? (
            <YearRangeSlider
              label="Over which years"
              min={0}
              max={last}
              from={ev.from}
              to={ev.to}
              format={offset => `Age ${ageOf(offset)}`}
              onChange={(from, to) => onPatch({ from, to, year: from })}
            />
          ) : (
            <AmountSlider
              label="When it happens"
              display={`Age ${ageOf(ev.year)}`}
              min={0}
              max={last}
              step={1}
              value={ev.year}
              onChange={year => onPatch({ year, from: year, to: year })}
            />
          )}
          <AmountSlider
            label={spec.valueLabel}
            display={val}
            min={0}
            max={frac ? 1 : Math.max(500000, Math.abs(ev.v) * 2)}
            step={frac ? 0.01 : 5000}
            value={Math.abs(ev.v)}
            onChange={raw => onPatch({ v: spec.defaultV < 0 ? -raw : raw })}
          />
        </div>
      ) : null}
      {ev.on ? (
        <div className="gc-b">
          <div className="gc-row">
            <span>When</span>
            <b>{when}</b>
          </div>
          <div className={`gc-row gc-sf ok`}>
            <span>{frac ? 'Impact' : 'Cost'}</span>
            <b>{val}</b>
          </div>
        </div>
      ) : null}
    </div>
  );
}
