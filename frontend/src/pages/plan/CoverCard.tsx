import { useEffect } from 'react';
import { Switch } from '../../components/ui';
import { Ico, NeedIcon } from '../../lib/icons';
import { needCardGap, needCardHave } from '../../lib/needEdit';
import {
  PLAN_FOR_NEED,
  clampAllWealthToCaps,
  clampCoverToCaps,
  clampPlanToCaps,
  coverSliderCaps,
  planAfford,
  planCoverPrem,
  planCoverSum,
  planIncluded,
  planLump,
  planMonthly,
  planNeedFunding,
  planSliderCaps,
  planTargetYear,
  setPlanCoverPatch,
  setPlanLumpPatch,
  setPlanMthPatch,
  sizedCover,
  togglePlanPatch,
} from '../../lib/planProducts';
import { InfoTip } from '../../components/InfoTip';
import {
  NET_RETURN_PCT_MAX,
  NET_RETURN_PCT_MIN,
  NET_RETURN_TIP,
  NET_RETURN_TRACK_GRADIENT,
  investRetFromReturn,
  netExpectedReturnColor,
  returnFromInvestRet,
} from '../../lib/assumptions';
import { netReturnCeiling, netReturnCeilingNote } from '../../lib/riskCapacity';
import { money, NEED_META, type GpSession, type NeedType } from '../../lib/types';

const SLIDER_TIPS = {
  sum: 'The lump this cover would pay if the insured event happens. Raise it to close more of the gap; lower it to cut the premium.',
  prem: 'What you would pay each year for this cover at the sum assured above. This is an illustration, not a quote from an insurer.',
  lump: 'A one-off amount from your investments put into this plan today. It then grows at the net expected return until the target year.',
  mth: 'How much of your free monthly budget this plan would take. It compounds at the net expected return until the target year.',
  net: NET_RETURN_TIP,
} as const;

export { sizedCover } from '../../lib/planProducts';

function PlanAffordWarn({ session }: { session: GpSession }) {
  const a = planAfford(session);
  const bits: string[] = [];
  if (a.monthlyOver > 0) {
    bits.push(`This plan is ${money(a.monthlyOver)}/mo over your free monthly budget.`);
  }
  if (a.lumpOver > 0) {
    bits.push(
      `Lump sums are ${money(a.lumpOver)} over your investments. Cash & Savings is not used for this check.`,
    );
  }
  if (!bits.length) return null;
  return <p className="x-affwarn">{bits.join(' ')}</p>;
}

export function coverOn(session: GpSession, type: NeedType) {
  return planIncluded(session, type);
}

export function AmountSlider({
  label,
  display,
  min,
  max,
  step,
  value,
  onChange,
  tip,
  tipWide,
  tone,
  ceiling,
  note,
}: {
  label: string;
  display: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (v: number) => void;
  tip?: string;
  tipWide?: boolean;
  tone?: 'net-return';
  /** Soft ceiling in the same units as min/max. Not clamped. */
  ceiling?: number;
  note?: string | null;
}) {
  const hi = Math.max(min, max);
  const clamped = Math.min(hi, Math.max(min, value));
  const net = tone === 'net-return';
  const accent = net ? netExpectedReturnColor(clamped) : undefined;
  const span = hi - min;
  const ceilT =
    ceiling != null && span > 0 ? Math.min(100, Math.max(0, ((ceiling - min) / span) * 100)) : null;
  return (
    <div
      className={net ? 'gsl gsl-net' : 'gsl'}
      style={
        accent
          ? {
              ['--net-accent' as string]: accent,
              ['--net-track' as string]: NET_RETURN_TRACK_GRADIENT,
            }
          : undefined
      }
    >
      <div className="gsl-h">
        <span className="gsl-lab">
          <label>{label}</label>
          {tip ? <InfoTip text={tip} label={label} wide={tipWide} /> : null}
        </span>
        <b>{display}</b>
      </div>
      <div className="gsl-railwrap">
        <input
          type="range"
          min={min}
          max={hi}
          step={step}
          value={clamped}
          aria-label={label}
          onChange={e => onChange(Number(e.target.value))}
        />
        {ceilT != null ? (
          <i className="gsl-ceil" style={{ left: `${ceilT}%` }} aria-hidden="true" />
        ) : null}
      </div>
      {net ? (
        <div className="gsl-ends" aria-hidden="true">
          <span>More likely</span>
          <span>Less likely</span>
        </div>
      ) : null}
      {note ? <p className="gsl-note">{note}</p> : null}
    </div>
  );
}

export function NeedShortfallBar({
  have,
  extra,
  req,
  lo = 'Projected savings',
  hi = 'Amount needed',
  planLabel = 'Private retirement plan contribution',
}: {
  have: number;
  extra: number;
  req: number;
  lo?: string;
  hi?: string;
  planLabel?: string;
}) {
  const havePct = req ? Math.max(0, Math.min(100, (have / req) * 100)) : 100;
  const planPct = req ? Math.max(0, Math.min(100 - havePct, (extra / req) * 100)) : 0;
  const covered = have + extra;
  const remain = req - covered;
  const over = remain < 0;
  const short = remain > 0;
  return (
    <div className="gc-b">
      <div className="gc-l">
        <span>{lo}</span>
        <b>{hi}</b>
      </div>
      <div className="gc-bar">
        {havePct > 0 ? <i style={{ width: `${havePct}%` }} /> : null}
        {planPct > 0 ? <i className="plan" style={{ width: `${planPct}%` }} /> : null}
      </div>
      <div className="gc-v">
        <span>{money(have)}</span>
        <b>{money(req)}</b>
      </div>
      <div className="gc-row gc-sf gc-plan">
        <span>{planLabel}</span>
        <b>{money(extra)}</b>
      </div>
      <div className={`gc-row gc-rem ${short || over ? 'no' : 'ok'}`}>
        <span>{short ? 'Shortfall' : 'Status'}</span>
        <b>{short ? money(remain) : over ? `Overfunded ${money(-remain)}` : 'Fully funded'}</b>
      </div>
    </div>
  );
}

export function CoverCard({
  type,
  title,
  on,
  sum,
  prem,
  onToggle,
  onEdit,
}: {
  type: NeedType;
  title: string;
  on: boolean;
  sum: number;
  prem: number;
  onToggle: () => void;
  onEdit: () => void;
}) {
  return (
    <div className={`gc ${on ? 'on' : ''}`}>
      <div className="gc-h">
        <span className="gc-ic" style={{ borderColor: on ? NEED_META[type].color : '#CDD2D8' }}>
          <NeedIcon type={type} />
        </span>
        <b>{title}</b>
        <button className="gc-x" type="button" aria-label={`Adjust ${title}`} onClick={onEdit}>
          {Ico.pencil}
        </button>
        <Switch on={on} label={title} onClick={onToggle} />
      </div>
      {on ? (
        <div className="gc-b">
          <div className="gc-row">
            <span>Sum assured</span>
            <b>{money(sum)}</b>
          </div>
          <div className="gc-row gc-sf">
            <span>Annual premium</span>
            <b>{money(prem)}</b>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function ProtectPlanCard({
  session,
  type,
  open,
  onToggleOpen,
  onChange,
}: {
  session: GpSession;
  type: NeedType;
  open: boolean;
  onToggleOpen: () => void;
  onChange: (p: Partial<GpSession>) => void;
}) {
  const title = PLAN_FOR_NEED[type];
  const meta = NEED_META[type];
  const on = planIncluded(session, type);
  const n = session.needs.find(x => x.type === type);
  if (!n) return null;
  const caps = coverSliderCaps(session, type);
  const rawSum = planCoverSum(session, type);
  const rawPrem = planCoverPrem(session, type);
  const sum = Math.min(rawSum, caps.sum);
  const prem = Math.min(rawPrem, caps.prem);
  const have = needCardHave(session, n);
  const req = n.needAmount || 0;
  const extra = on ? sum : 0;

  useEffect(() => {
    if (rawSum > caps.sum || rawPrem > caps.prem) onChange(clampCoverToCaps(session, type));
  }, [rawSum, rawPrem, caps.sum, caps.prem, onChange, session, type]);

  return (
    <div className={`gc ${on ? 'on' : ''}${open ? ' open' : ''}`}>
      <div className="gc-h">
        <button
          className="gc-exp"
          type="button"
          aria-expanded={open}
          aria-label={open ? `Collapse ${title}` : `Expand ${title}`}
          onClick={onToggleOpen}
        >
          <span className="gc-ic" style={{ borderColor: on ? meta.color : '#CDD2D8' }}>
            <NeedIcon type={type} />
          </span>
          <b>{title}</b>
        </button>
        <button
          className="gc-x"
          type="button"
          aria-label={open ? `Collapse ${title}` : `Expand ${title}`}
          aria-expanded={open}
          onClick={onToggleOpen}
        >
          {Ico.chev}
        </button>
        <Switch on={on} label={title} onClick={() => onChange(togglePlanPatch(session, type))} />
      </div>
      {open ? (
        <div className="gc-e">
          <AmountSlider
            label="Sum assured"
            tip={SLIDER_TIPS.sum}
            display={money(sum)}
            min={0}
            max={caps.sum}
            step={1000}
            value={sum}
            onChange={v => onChange(setPlanCoverPatch(session, type, { sum: v }))}
          />
          <AmountSlider
            label="Annual premium"
            tip={SLIDER_TIPS.prem}
            display={money(prem)}
            min={0}
            max={caps.prem}
            step={10}
            value={prem}
            onChange={v => onChange(setPlanCoverPatch(session, type, { prem: v }))}
          />
          <PlanAffordWarn session={session} />
        </div>
      ) : null}
      <NeedShortfallBar
        have={have}
        extra={extra}
        req={req}
        lo={meta.lo}
        hi={meta.hi}
        planLabel={`${title} contribution`}
      />
    </div>
  );
}

export function GrowthPlanCard({
  session,
  type,
  open,
  onToggleOpen,
  onChange,
}: {
  session: GpSession;
  type: NeedType;
  open: boolean;
  onToggleOpen: () => void;
  onChange: (p: Partial<GpSession>) => void;
}) {
  const title = PLAN_FOR_NEED[type];
  const on = planIncluded(session, type);
  const n = session.needs.find(x => x.type === type);
  if (!n) return null;
  const caps = planSliderCaps(session, type);
  const rawLump = planLump(session, type);
  const rawMth = planMonthly(session, type);
  const lump = Math.min(rawLump, caps.lump);
  const mth = Math.min(rawMth, caps.monthly);
  const { have, extra, req } = planNeedFunding(session, type, lump, mth);
  const byYear = planTargetYear(session, type);

  useEffect(() => {
    if (rawLump > caps.lump || rawMth > caps.monthly) onChange(clampPlanToCaps(session, type));
  }, [rawLump, rawMth, caps.lump, caps.monthly, onChange, session, type]);
  return (
    <div className={`gc ${on ? 'on' : ''}${open ? ' open' : ''}`}>
      <div className="gc-h">
        <button
          className="gc-exp"
          type="button"
          aria-expanded={open}
          aria-label={open ? `Collapse ${title}` : `Expand ${title}`}
          onClick={onToggleOpen}
        >
          <span className="gc-ic" style={{ borderColor: on ? NEED_META[type].color : '#CDD2D8' }}>
            <NeedIcon type={type} />
          </span>
          <b>{title}</b>
        </button>
        <span className="gc-by">by {byYear}</span>
        <button
          className="gc-x"
          type="button"
          aria-label={open ? `Collapse ${title}` : `Expand ${title}`}
          aria-expanded={open}
          onClick={onToggleOpen}
        >
          {Ico.chev}
        </button>
        <Switch on={on} label={title} onClick={() => onChange(togglePlanPatch(session, type))} />
      </div>
      {open ? (
        <div className="gc-e">
          <AmountSlider
            label="Lump sum to invest"
            tip={SLIDER_TIPS.lump}
            display={money(lump)}
            min={0}
            max={caps.lump}
            step={1000}
            value={lump}
            onChange={v => onChange(setPlanLumpPatch(session, type, v))}
          />
          <AmountSlider
            label="Monthly contribution"
            tip={SLIDER_TIPS.mth}
            display={money(mth)}
            min={0}
            max={caps.monthly}
            step={50}
            value={mth}
            onChange={v => onChange(setPlanMthPatch(session, type, v))}
          />
          <AmountSlider
            label="Net expected returns"
            tip={SLIDER_TIPS.net}
            tipWide
            tone="net-return"
            display={`${investRetFromReturn(session.investmentReturn).toFixed(1)}% p.a.`}
            min={NET_RETURN_PCT_MIN}
            max={NET_RETURN_PCT_MAX}
            step={0.1}
            value={investRetFromReturn(session.investmentReturn)}
            ceiling={netReturnCeiling(session.riskProfile) * 100}
            note={netReturnCeilingNote(session.investmentReturn, session.riskProfile)}
            onChange={v => {
              const investmentReturn = returnFromInvestRet(v);
              const investRet = investRetFromReturn(investmentReturn);
              onChange({
                investRet,
                investmentReturn,
                investmentReturnTouched: true,
                ...clampAllWealthToCaps({ ...session, investRet, investmentReturn }),
              });
            }}
          />
          <PlanAffordWarn session={session} />
        </div>
      ) : null}
      <NeedShortfallBar
        have={have}
        extra={extra}
        req={req}
        planLabel={`${title} contribution`}
      />
    </div>
  );
}

export function AddPlanPanel({
  session,
  type,
  on,
  onToggle,
}: {
  session: GpSession;
  type: NeedType;
  on: boolean;
  onToggle: () => void;
}) {
  const meta = NEED_META[type];
  const n = session.needs.find(x => x.type === type);
  if (!n) return <p className="x-sm">No matching shortfall to close.</p>;
  const have = needCardHave(session, n);
  const req = n.needAmount || 0;
  const gap = needCardGap(session, n);
  const pct = req ? Math.max(have > 0 ? 2 : 0, Math.min(100, (have / req) * 100)) : 100;
  const { sum, prem } = sizedCover(session, type);
  const wealth = meta.group === 'w';
  const title = PLAN_FOR_NEED[type];
  return (
    <div className={`gc on${on ? ' open' : ''}`}>
      <div className="gc-h">
        <span className="gc-ic" style={{ borderColor: meta.color }}>
          <NeedIcon type={type} />
        </span>
        <b>{title}</b>
        <Switch on={on} label={title} onClick={onToggle} />
      </div>
      <div className="gc-b">
        <div className="gc-l">
          <span>{meta.lo}</span>
          <b>{meta.hi}</b>
        </div>
        <div className="gc-bar">
          <i style={{ width: `${pct}%` }} />
        </div>
        <div className="gc-v">
          <span>{money(have)}</span>
          <b>{money(req)}</b>
        </div>
        {wealth ? (
          <>
            <div className={`gc-row gc-sf ${gap > 0 ? 'no' : 'ok'}`}>
              <span>{gap > 0 ? 'Shortfall' : 'Status'}</span>
              <b>{gap > 0 ? money(gap) : 'Fully funded'}</b>
            </div>
            <div className="gc-row gc-sf ok">
              <span>This plan · monthly contribution</span>
              <b>{money(planMonthly(session, type))}</b>
            </div>
          </>
        ) : (
          <>
            <div className="gc-row gc-sf gc-plan">
              <span>{title} contribution</span>
              <b>{money(on ? sum : 0)}</b>
            </div>
            <div className={`gc-row gc-rem ${gap - (on ? sum : 0) > 0 ? 'no' : 'ok'}`}>
              <span>{gap - (on ? sum : 0) > 0 ? 'Shortfall' : 'Status'}</span>
              <b>
                {gap - (on ? sum : 0) > 0
                  ? money(gap - (on ? sum : 0))
                  : gap - (on ? sum : 0) < 0
                    ? `Overfunded ${money((on ? sum : 0) - gap)}`
                    : 'Fully funded'}
              </b>
            </div>
            <div className="gc-row">
              <span>Annual premium</span>
              <b>{money(prem)}</b>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
