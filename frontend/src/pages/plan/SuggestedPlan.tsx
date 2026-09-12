import { useEffect, type Dispatch, type RefObject, type SetStateAction } from 'react';
import { NEED_GROUPS } from '../../components/GoalCard';
import { HappiUGauge } from '../../components/HappiUGauge';
import { GroupTag, NarrBtn, Switch } from '../../components/ui';
import type { ExplainKind } from '../../lib/explain';
import { Ico } from '../../lib/icons';
import { PLAN_FOR_NEED, allPlansOn, planAfford, planRemain, suggestedInGroup, suggestedNeeds, toggleAllPlansPatch } from '../../lib/planProducts';
import {
  EXTRA_NEEDS,
  HAPPI_COL,
  happiBand,
  happiCaption,
  NEED_META,
  money,
  moneyK,
  type ExtraNeed,
  type GpSession,
  type NeedType,
} from '../../lib/types';
import { GrowthPlanCard, ProtectPlanCard } from './CoverCard';

function FitRow({
  label,
  value,
  kind,
}: {
  label: string;
  value: string;
  kind?: 'hi' | 'ok' | 'no';
}) {
  return (
    <div className={`row${kind ? ` ${kind}` : ''}`}>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function PlanAffordPanel({ session }: { session: GpSession }) {
  const a = planAfford(session);
  const monthlyOver = a.monthlyOver > 0;
  const lumpOver = a.lumpOver > 0;
  return (
    <>
      <div className="x-prod-fitg x-prod-bud">
        <FitRow label="Monthly available budget" value={money(a.available)} kind="hi" />
        <FitRow label={`Recommended free budget (${a.freePct}%)`} value={money(a.free)} />
        <FitRow label="Protection premiums" value={`${money(a.premMth)}/mo`} />
        <FitRow label="Monthly contributions" value={`${money(a.contribMth)}/mo`} />
        <FitRow
          label={monthlyOver ? 'Over free budget' : 'Within free budget'}
          value={monthlyOver ? money(a.monthlyOver) : 'Fits'}
          kind={monthlyOver ? 'no' : 'ok'}
        />
      </div>
      <div className="x-prod-fitg x-prod-sav">
        <FitRow label="Investments" value={money(a.investments ?? a.savings)} kind="hi" />
        <FitRow label="Plan lump sums" value={money(a.lumps)} />
        <FitRow
          label={lumpOver ? 'Over investments' : 'Within investments'}
          value={lumpOver ? money(a.lumpOver) : 'Fits'}
          kind={lumpOver ? 'no' : 'ok'}
        />
      </div>
    </>
  );
}

export function SuggestedPlan({
  session,
  score,
  planOpen,
  setPlanOpen,
  editProd,
  setEditProd,
  planModal,
  setPlanModal,
  onChange,
  onToggleExtra,
  narrKind,
  narrPaused,
  onNarr,
  mixRef,
  gapRef,
  gapType,
}: {
  session: GpSession;
  score: number;
  planOpen: boolean;
  setPlanOpen: Dispatch<SetStateAction<boolean>>;
  editProd: NeedType | null;
  setEditProd: Dispatch<SetStateAction<NeedType | null>>;
  planModal: NeedType | null;
  setPlanModal: Dispatch<SetStateAction<NeedType | null>>;
  onChange: (p: Partial<GpSession>) => void;
  onToggleExtra: (k: ExtraNeed) => void;
  narrKind: string | null;
  narrPaused?: boolean;
  onNarr: (kind: ExplainKind) => void;
  mixRef?: RefObject<HTMLDivElement | null>;
  gapRef?: RefObject<HTMLButtonElement | null>;
  gapType?: NeedType | null;
}) {
  const suggested = suggestedNeeds(session);
  const plansOn = allPlansOn(session);
  const toggleEdit = (type: NeedType) => setEditProd(p => (p === type ? null : type));

  useEffect(() => {
    if (!planModal) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPlanModal(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [planModal, setPlanModal]);

  const planCard = (type: NeedType, open: boolean, onToggleOpen: () => void) =>
    NEED_META[type].group === 'p' ? (
      <ProtectPlanCard
        session={session}
        type={type}
        open={open}
        onToggleOpen={onToggleOpen}
        onChange={onChange}
      />
    ) : (
      <GrowthPlanCard
        session={session}
        type={type}
        open={open}
        onToggleOpen={onToggleOpen}
        onChange={onChange}
      />
    );

  const col = (group: 'p' | 'w') => {
    const meta = NEED_GROUPS[group];
    const rows = suggestedInGroup(session, group);
    const extras =
      group === 'p'
        ? EXTRA_NEEDS.filter(x => session.extraNeeds.includes(x.k)).map(x => (
            <div key={x.k} className="gc on">
              <div className="gc-h">
                <span className="gc-ic" style={{ borderColor: x.color }}>
                  <span className="need-ico">{x.k === 'hosp' ? '🏨' : '🩹'}</span>
                </span>
                <b>{x.label}</b>
                <Switch on label={x.label} onClick={() => onToggleExtra(x.k)} />
              </div>
            </div>
          ))
        : [];
    return (
      <div className="x-prodg">
        <div className="x-prodh">
          <b>{meta.title}</b>
          <span>{meta.blurb}</span>
        </div>
        <div className="x-prodl">
          {rows.map(n => (
            <div key={n.type}>{planCard(n.type, editProd === n.type, () => toggleEdit(n.type))}</div>
          ))}
          {extras}
          {!rows.length && !extras.length ? <p className="x-sm">No shortfall to close in this group.</p> : null}
        </div>
      </div>
    );
  };

  return (
    <div className={`x-needs x-prod${planOpen ? ' open' : ''}`}>
      <div className="x-needsh x-prod-head">
        <button
          className="x-needsh-t"
          type="button"
          aria-expanded={planOpen}
          onClick={() => setPlanOpen(open => !open)}
        >
          <b>Suggested plan</b>
          <GroupTag session={session} keys={[]} verb="usually consider this" />
        </button>
        {planOpen ? (
          <NarrBtn
            label="Explain plan's benefits"
            on={narrKind === 'prod'}
            paused={narrPaused}
            onClick={() => onNarr('prod')}
          />
        ) : null}
        {suggested.length ? (
          <div className="x-prod-apply">
            <span>Apply this plan</span>
            <Switch
              on={plansOn}
              label={plansOn ? 'Stop applying this plan' : 'Apply this plan'}
              onClick={() => onChange(toggleAllPlansPatch(session))}
            />
          </div>
        ) : null}
        <button
          className="cv"
          type="button"
          aria-expanded={planOpen}
          aria-label={planOpen ? 'Collapse suggested plan' : 'Expand suggested plan'}
          onClick={() => setPlanOpen(open => !open)}
        >
          {Ico.chev}
        </button>
      </div>
      {planOpen ? (
        <>
          <div className="x-prod-hero">
            <div className="x-prod-gauge x-prod-fitg">
              <HappiUGauge value={score} size={280} showBand={false} />
              <p className="x-scorecap" style={{ color: HAPPI_COL[happiBand(score)] }}>
                {happiCaption(score)}
              </p>
            </div>
            <PlanAffordPanel session={session} />
          </div>
          <div className="x-need-cols">
            {col('p')}
            {col('w')}
          </div>
        </>
      ) : (
        <div ref={mixRef} className="x-prod-sum">
          <div className="x-prod-tags">
            {suggested.length ? (
              suggested.map(n => {
                const title = PLAN_FOR_NEED[n.type];
                const remain = planRemain(session, n.type);
                const short = remain > 0;
                const gapHit = gapType === n.type;
                return (
                  <div key={n.type} className={`x-chip ${short ? 'no' : 'ok'}`}>
                    <button className="x-chip-lab" type="button" onClick={() => setPlanOpen(true)}>
                      {short ? (
                        `${title} Shortfall: ${moneyK(remain)}`
                      ) : (
                        <>
                          {title} {Ico.check}
                        </>
                      )}
                    </button>
                    <button
                      ref={gapHit ? gapRef : undefined}
                      className={`x-chip-edit${gapHit ? ' x-coach-hit' : ''}`}
                      type="button"
                      aria-label={`Adjust ${title}`}
                      onClick={() => setPlanModal(n.type)}
                    >
                      {Ico.pencil}
                    </button>
                  </div>
                );
              })
            ) : (
              <span className="x-sm">Every activated goal is already funded.</span>
            )}
          </div>
          <NarrBtn
            label="Explain plan's benefits"
            on={narrKind === 'prod'}
            paused={narrPaused}
            onClick={() => onNarr('prod')}
          />
        </div>
      )}
      {planModal ? (
        <div className="x-modal" role="dialog" aria-modal="true" aria-label={PLAN_FOR_NEED[planModal]}>
          <div className="x-modal-bd" onClick={() => setPlanModal(null)} />
          <div className="x-modal-w x-modal-gc">
            <button className="x-modal-x" type="button" aria-label="Close" onClick={() => setPlanModal(null)}>
              {Ico.close}
            </button>
            {planCard(planModal, true, () => setPlanModal(null))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
