import type { ReactNode } from 'react';
import {
  LIFESTYLE,
  moneyMax,
  nowYear,
  surplusAnnual,
  yearsWord,
  type NeedEdit,
} from '../lib/needEdit';
import { money, sessionAge, type GpSession, type NeedRow, type NeedType } from '../lib/types';

function SliderRow({
  label,
  display,
  min,
  max,
  step,
  value,
  onChange,
  note,
}: {
  label: string;
  display: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (v: number) => void;
  note?: ReactNode;
}) {
  const hi = Math.max(min, max);
  const clamped = Math.min(hi, Math.max(min, value));
  return (
    <div className="gsl">
      <div className="gsl-h">
        <label>{label}</label>
        <b>{display}</b>
      </div>
      {note ? <div className="gsl-note">{note}</div> : null}
      <input
        type="range"
        min={min}
        max={hi}
        step={step}
        value={clamped}
        aria-label={label}
        onChange={e => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function SegRow({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { v: string | number; label: string }[];
  value: string | number;
  onChange: (v: string | number) => void;
}) {
  return (
    <div className="gsl">
      <div className="gsl-h">
        <label>{label}</label>
      </div>
      <div className="gseg">
        {options.map(o => (
          <button
            key={String(o.v)}
            type="button"
            className={o.v === value ? 'on' : ''}
            aria-pressed={o.v === value}
            onClick={() => onChange(o.v)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function GoalEditor({
  session,
  type,
  n,
  e,
  onPatch,
}: {
  session: GpSession;
  type: NeedType;
  n: NeedRow;
  e: NeedEdit;
  onPatch: (p: Partial<NeedRow>) => void;
}) {
  const age = sessionAge(session) || 40;
  const y = nowYear();
  const inc = session.incomeMonthly || 0;
  const liq = (session.cash || 0) + (session.investments || 0);

  if (type === 'N_RET') {
    return (
      <>
        <SliderRow
          label="Retirement age"
          display={`Age ${e.retAge}`}
          min={Math.max(50, age + 1)}
          max={75}
          step={1}
          value={e.retAge}
          onChange={v => onPatch({ retAge: v })}
        />
        <SegRow
          label="Retirement lifestyle"
          options={LIFESTYLE.map(x => ({ v: x.v, label: x.label }))}
          value={e.lifestyle}
          onChange={v => onPatch({ lifestyle: Number(v) })}
        />
        <SliderRow
          label="Amount already set aside"
          display={money(e.existing)}
          min={0}
          max={moneyMax(liq, 500000)}
          step={500}
          value={e.existing}
          onChange={v => onPatch({ existing: v })}
        />
        <SliderRow
          label="Existing monthly contribution"
          display={`${money(e.monthlyContribution)}/mo`}
          min={0}
          max={moneyMax(Math.max(inc - (session.expenseMonthly || 0), 2000), 5000)}
          step={50}
          value={e.monthlyContribution}
          onChange={v => onPatch({ monthlyContribution: v })}
        />
      </>
    );
  }

  if (type === 'N_INC') {
    return (
      <>
        <SliderRow
          label="Years of support for the family"
          display={yearsWord(e.dependYears)}
          min={1}
          max={40}
          step={1}
          value={e.dependYears}
          onChange={v => onPatch({ dependYears: v })}
          note={`Covers ${money(session.expenseMonthly || 0)}/mo of household spending`}
        />
        <SliderRow
          label="Liabilities to settle"
          display={money(e.liabilities)}
          min={0}
          max={moneyMax(session.mortgage || 0, 200000)}
          step={1000}
          value={e.liabilities}
          onChange={v => onPatch({ liabilities: v })}
        />
        <SliderRow
          label="Legacy to leave behind"
          display={money(e.bequest)}
          min={0}
          max={moneyMax(e.bequest, 500000)}
          step={5000}
          value={e.bequest}
          onChange={v => onPatch({ bequest: v })}
        />
        <SliderRow
          label="Existing cover in force"
          display={money(e.existing)}
          min={0}
          max={moneyMax(n.needAmount || 0, 500000)}
          step={5000}
          value={e.existing}
          onChange={v => onPatch({ existing: v })}
        />
      </>
    );
  }

  if (type === 'N_HOS') {
    return (
      <SliderRow
        label="Existing cover in force"
        display={money(e.existing)}
        min={0}
        max={moneyMax(n.needAmount || 0, 500000)}
        step={5000}
        value={e.existing}
        onChange={v => onPatch({ existing: v })}
        note={`Six months of income at ${money(inc)}/mo`}
      />
    );
  }

  if (type === 'N_CRI' || type === 'N_TPD') {
    return (
      <>
        <SliderRow
          label="Monthly income to replace"
          display={`${money(e.incomeReplaceMonthly)}/mo`}
          min={0}
          max={moneyMax(inc, 20000)}
          step={100}
          value={e.incomeReplaceMonthly}
          onChange={v => onPatch({ incomeReplaceMonthly: v })}
        />
        <SliderRow
          label="Existing cover in force"
          display={money(e.existing)}
          min={0}
          max={moneyMax(n.needAmount || 0, 500000)}
          step={5000}
          value={e.existing}
          onChange={v => onPatch({ existing: v })}
        />
      </>
    );
  }

  if (type === 'N_EDU') {
    return (
      <>
        <SliderRow
          label="Year study begins"
          display={String(e.targetYear)}
          min={y}
          max={y + 30}
          step={1}
          value={e.targetYear}
          onChange={v => onPatch({ targetYear: v, fundsNeededYear: v })}
          note="A Singapore degree, grown with inflation to that year"
        />
        <SliderRow
          label="Funds set aside for education"
          display={money(e.existing)}
          min={0}
          max={moneyMax(liq, 200000)}
          step={500}
          value={e.existing}
          onChange={v => onPatch({ existing: v })}
        />
      </>
    );
  }

  const amountLabel = type === 'N_PRP' ? 'Amount required' : 'Amount required';
  const setAsideLabel = type === 'N_PRP' ? 'Amount already set aside' : 'Amount already set aside';
  return (
    <>
      <SliderRow
        label="Target year"
        display={String(e.targetYear)}
        min={y}
        max={y + 40}
        step={1}
        value={e.targetYear}
        onChange={v => onPatch({ targetYear: v, fundsNeededYear: v })}
      />
      <SliderRow
        label={amountLabel}
        display={money(e.amountRequired)}
        min={0}
        max={moneyMax(0, 5_000_000)}
        step={5000}
        value={e.amountRequired}
        onChange={v => onPatch({ needAmount: v })}
      />
      <SliderRow
        label={setAsideLabel}
        display={money(e.existing)}
        min={0}
        max={moneyMax(liq, 200000)}
        step={500}
        value={e.existing}
        onChange={v => onPatch({ existing: v })}
      />
      <SliderRow
        label="Existing monthly contribution"
        display={`${money(e.monthlyContribution)}/mo`}
        min={0}
        max={moneyMax(Math.max(inc - (session.expenseMonthly || 0), 2000), 5000)}
        step={50}
        value={e.monthlyContribution}
        onChange={v => onPatch({ monthlyContribution: v })}
      />
      <SliderRow
        label="Contributing for"
        display={yearsWord(e.contributeYears)}
        min={1}
        max={40}
        step={1}
        value={e.contributeYears}
        onChange={v => onPatch({ contributeYears: v })}
      />
    </>
  );
}

export function bannerFor(session: GpSession, type: NeedType, e: NeedEdit): string | null {
  const age = sessionAge(session);
  if (type === 'N_RET' && age) {
    const yrs = Math.max(0, e.retAge - age);
    return `Age ${age} · ${yearsWord(yrs)} to a normal retirement date`;
  }
  if (type === 'N_INC') {
    const d = e.dependants;
    const dep = `${d} dependant${d === 1 ? '' : 's'}`;
    return `${dep} and ${money(e.liabilities)} of debt outstanding`;
  }
  if (type === 'N_SAV') {
    const left = surplusAnnual(session);
    if (!left) return 'Unallocated saving needs a target to be worth anything';
    return `${money(left)} a year left over · unallocated saving needs a target to be worth anything`;
  }
  return null;
}
