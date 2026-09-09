import { useEffect, useRef, useState, type ReactNode } from 'react';
import { EqPie, Tip } from '../../components/ui';
import { Ico } from '../../lib/icons';
import { COVER_FIELD_SLIDER, moneyMax } from '../../lib/needEdit';
import { coverPrem, coverSum, money, POLICY_COL, POLICY_TYPES, type GpSession, type Policy } from '../../lib/types';

type CoverDraft = { type: string; insurer: string; sum: number; premium: number };

const BLANK_COVER: CoverDraft = {
  type: 'Life Protection',
  insurer: 'Existing insurer',
  sum: 0,
  premium: 0,
};

function snap(n: number, step: number) {
  return Math.max(0, Math.round((Number(n) || 0) / step) * step);
}

function sliderMax(n: number, floor: number, step: number) {
  return Math.max(step, Math.ceil(moneyMax(n, floor) / step) * step);
}

function toPolicy(d: CoverDraft): Policy {
  return {
    type: d.type || 'Life Protection',
    insurer: d.insurer.trim() || 'Existing insurer',
    sum: Math.max(0, Math.round(d.sum || 0)),
    premium: Math.max(0, Math.round(d.premium || 0)),
  };
}

function asDraft(r: Policy): CoverDraft {
  return {
    type: r.type || 'Life Protection',
    insurer: r.insurer || 'Existing insurer',
    sum: r.sum || 0,
    premium: r.premium || 0,
  };
}

function isBlank(d: CoverDraft) {
  return (
    !d.sum &&
    !d.premium &&
    d.type === BLANK_COVER.type &&
    (!d.insurer.trim() || d.insurer.trim() === BLANK_COVER.insurer)
  );
}

function CoverAmtSlider({
  label,
  value,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  const hi = Math.max(step, max);
  const clamped = Math.min(hi, snap(value, step));
  return (
    <label>
      {label}
      <div className="gsl">
        <div className="gsl-h">
          <b>{money(clamped)}</b>
        </div>
        <input
          type="range"
          min={0}
          max={hi}
          step={step}
          value={clamped}
          aria-label={label}
          onChange={e => onChange(Number(e.target.value))}
        />
        <div className="gsl-ends">
          <span>{money(0)}</span>
          <span>{money(hi)}</span>
        </div>
      </div>
    </label>
  );
}

function CoverForm({
  title,
  value,
  onChange,
}: {
  title: string;
  value: CoverDraft;
  onChange: (d: CoverDraft) => void;
}) {
  const cap = useRef({
    sum: sliderMax(value.sum, COVER_FIELD_SLIDER.sum.floor, COVER_FIELD_SLIDER.sum.step),
    premium: sliderMax(value.premium, COVER_FIELD_SLIDER.premium.floor, COVER_FIELD_SLIDER.premium.step),
  });
  return (
    <>
      <b>{title}</b>
      <div className="x-covf">
        <label>
          Type of cover
          <select
            className="x-in"
            value={value.type}
            aria-label="Type of cover"
            onChange={e => onChange({ ...value, type: e.target.value })}
          >
            {([value.type, ...POLICY_TYPES] as string[])
              .filter((t, i, all) => t && t !== 'Education' && all.indexOf(t) === i)
              .map(t => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
          </select>
        </label>
        <label>
          Insurer
          <input
            className="x-in"
            value={value.insurer}
            aria-label="Insurer"
            onChange={e => onChange({ ...value, insurer: e.target.value })}
          />
        </label>
        <CoverAmtSlider
          label="Sum assured"
          value={value.sum}
          max={cap.current.sum}
          step={COVER_FIELD_SLIDER.sum.step}
          onChange={sum => onChange({ ...value, sum })}
        />
        <CoverAmtSlider
          label="Annual premium"
          value={value.premium}
          max={cap.current.premium}
          step={COVER_FIELD_SLIDER.premium.step}
          onChange={premium => onChange({ ...value, premium })}
        />
      </div>
    </>
  );
}

function AddCoverForm({
  title,
  onCommit,
}: {
  title: string;
  onCommit: (d: CoverDraft | null) => void;
}) {
  const [draft, setDraft] = useState(BLANK_COVER);
  const draftRef = useRef(draft);
  draftRef.current = draft;
  const commitRef = useRef(onCommit);
  commitRef.current = onCommit;
  useEffect(() => {
    return () => {
      const d = draftRef.current;
      commitRef.current(isBlank(d) ? null : d);
    };
  }, []);
  return <CoverForm title={title} value={draft} onChange={setDraft} />;
}

export function CoverBlock({
  session,
  onChange,
  tipBody,
}: {
  session: GpSession;
  onChange: (p: Partial<GpSession>) => void;
  tipBody: ReactNode;
}) {
  const pol = session.policies;
  const sumA = coverSum(session);
  const prem = coverPrem(session);
  const toggleTip = (id: string) => onChange({ tip: session.tip === id ? null : id });
  const markYou = (policies: Policy[]) =>
    onChange({
      policies,
      provenance: { ...session.provenance, cover: 'you' },
      moneyTouched: { ...session.moneyTouched, cover: true },
      tip: null,
    });
  const patchPolicy = (index: number, d: CoverDraft) =>
    onChange({
      policies: pol.map((p, i) => (i === index ? toPolicy(d) : p)),
      provenance: { ...session.provenance, cover: 'you' },
      moneyTouched: { ...session.moneyTouched, cover: true },
    });
  const commitAdd = (d: CoverDraft | null) => {
    if (!d) return;
    markYou([...pol, toPolicy(d)]);
  };
  const addForm = (title: string) => <AddCoverForm title={title} onCommit={commitAdd} />;
  return (
    <>
      <EqPie
        rows={pol.map(r => ({
          l: r.type,
          v: r.sum,
          fill: POLICY_COL[r.type] || '#7086FD',
        }))}
      />
      {pol.length ? (
        pol.map((r, i) => (
          <div className="t pol" key={i}>
            <span>
              <i className="pd" style={{ background: POLICY_COL[r.type] || '#7086FD' }} />
              {r.type}
              <em className="rsub">
                &nbsp;· {r.insurer} · {money(r.premium)} a year
              </em>
            </span>
            <b>{money(r.sum)}</b>
            <Tip id={`ecov-${i}`} open={session.tip} onToggle={toggleTip} edit right wide>
              <CoverForm title="Edit cover" value={asDraft(r)} onChange={d => patchPolicy(i, d)} />
            </Tip>
            <button
              className="x-rmv"
              type="button"
              aria-label="Remove this policy"
              onClick={() => markYou(pol.filter((_, j) => j !== i))}
            >
              {Ico.close}
            </button>
          </div>
        ))
      ) : (
        <div className="t none">
          <span>No cover recorded yet — add what you hold so your gaps are honest.</span>
          <b>—</b>
          <Tip id="ecov-new" open={session.tip} onToggle={toggleTip} edit right wide>
            {addForm('Add cover')}
          </Tip>
        </div>
      )}
      {pol.length ? (
        <div className="add">
          <span>Add another cover</span>
          <Tip id="ecov-new" open={session.tip} onToggle={toggleTip} edit right wide>
            {addForm('Add cover')}
          </Tip>
        </div>
      ) : null}
      <div className="tot">
        <span>
          Total sum assured
          <Tip id="icov" open={session.tip} onToggle={toggleTip} right>
            {tipBody}
          </Tip>
          {pol.length ? <em className="rsub">&nbsp;· {money(prem)} a year in premiums</em> : null}
        </span>
        <b>{pol.length ? money(sumA) : '—'}</b>
      </div>
    </>
  );
}
