import { useEffect, useRef, useState } from 'react';
import { CoachTour } from '../components/CoachTour';
import { HappiUGauge } from '../components/HappiUGauge';
import { GoalCard, NeedGroups } from '../components/GoalCard';
import { InfoTip } from '../components/InfoTip';
import { Foot, GroupTag, NarrBtn } from '../components/ui';
import { X_RATIO_WHY } from '../lib/catalog';
import type { ExplainKind } from '../lib/explain';
import { Ico } from '../lib/icons';
import { applyNeedPatch, capEnabledNeeds, needCardGap } from '../lib/needEdit';
import { moneyRatios, rnum, type Ratio } from '../lib/ratios';
import {
  RISK_ABILITY_TIP,
  RISK_LEVELS,
  RISK_TRACK_GRADIENT,
  clampRiskProfile,
  riskCapacity,
  riskLevel,
  suitableRisk,
} from '../lib/riskCapacity';
import {
  EXTRA_NEEDS,
  HAPPI_COL,
  firstName,
  happiBand,
  happiCaption,
  moneyK,
  NEED_META,
  type ExtraNeed,
  type GpSession,
  type NeedType,
} from '../lib/types';

export function Score({
  session,
  pre,
  scoreError,
  onChange,
  onBack,
  onPlan,
  onToggleNeed,
  onToggleExtra,
  busy,
  narrKind,
  narrPaused,
  onNarr,
  gtTtOn,
  onGtTtComplete,
}: {
  session: GpSession;
  pre: number | null;
  scoreError?: string | null;
  onChange: (p: Partial<GpSession>) => void;
  onBack: () => void;
  onPlan: (need?: NeedType) => void;
  onToggleNeed: (t: NeedType) => void;
  onToggleExtra: (k: ExtraNeed) => void;
  busy: boolean;
  narrKind: ExplainKind | null;
  narrPaused?: boolean;
  onNarr: (kind: ExplainKind) => void;
  gtTtOn: boolean;
  onGtTtComplete: () => void;
}) {
  const score = pre ?? 0;
  const band = happiBand(score);
  const read = happiCaption(score);
  const onNeeds = session.needs.filter(n => n.enabled);
  const taggedNeeds = [...onNeeds]
    .map(n => ({ ...n, gap: needCardGap(session, n) }))
    .sort((a, b) => (b.gap || 0) - (a.gap || 0));
  const R = moneyRatios({
    income: session.incomeMonthly,
    expense: session.expenseMonthly,
    cash: session.cash,
    investments: session.investments,
    property: session.property,
    mortgage: session.mortgage,
  });
  const offNeeds = session.needs.filter(n => !n.enabled);
  const offExtra = EXTRA_NEEDS.filter(x => !session.extraNeeds.includes(x.k));
  const okRatios = R.filter(r => r.ok).length;
  const badRatios = R.length - okRatios;
  const ratioTone = badRatios === 0 ? 'ok' : badRatios <= 3 ? 'warn' : 'no';
  const ratioStatus =
    badRatios === 0
      ? 'All in good shape'
      : `${badRatios} ${badRatios === 1 ? 'needs' : 'need'} attention`;
  const [needsOpen, setNeedsOpen] = useState(false);
  const [healthOpen, setHealthOpen] = useState(false);
  const [riskOpen, setRiskOpen] = useState(false);
  const [editNeed, setEditNeed] = useState<NeedType | null>(null);
  const scoreRef = useRef<HTMLDivElement>(null);
  const needsRef = useRef<HTMLDivElement>(null);
  const ratiosRef = useRef<HTMLButtonElement>(null);
  const riskRef = useRef<HTMLButtonElement>(null);
  const cap = riskCapacity(session);
  const ability = riskLevel(cap.capacity);
  const tolerance = clampRiskProfile(session.riskTolerance ?? 3);
  const comfort = riskLevel(tolerance);
  const suitable = riskLevel(suitableRisk(cap.capacity, tolerance));
  const riskChip = `Risk: ${suitable.label}`;
  const closeModal = () => setEditNeed(null);
  const who = firstName(session);
  const chipNeeds = (() => {
    const tagged = session.needs.map(n => ({ ...n, gap: needCardGap(session, n) }));
    const on = tagged.filter(n => n.enabled);
    const prot = on.filter(n => NEED_META[n.type].group === 'p').sort((a, b) => (b.gap || 0) - (a.gap || 0));
    const grow = on.filter(n => NEED_META[n.type].group === 'w').sort((a, b) => (b.gap || 0) - (a.gap || 0));
    return [...prot.slice(0, 2), ...grow.slice(0, 2)];
  })();
  const shortN = taggedNeeds.filter(n => n.gap > 0).length;
  const fundedN = taggedNeeds.length - shortN;
  const scoreReady = pre != null;
  const bandLabel = band === 'GOOD' ? 'Good' : band === 'FAIR' ? 'Fair' : 'Poor';
  const scoreTip = `${Math.round(score)} out of 100 is ${bandLabel}. HappiU is one score for how well your money holds up: below 50 is Poor, 50 to 84 is Fair, and 85 and above is Good.`;
  const needsTip =
    `${taggedNeeds.length === 1 ? 'This goal' : 'These goals and needs'} come from a demographic cohort like ${who}. ` +
    `${shortN} ${shortN === 1 ? 'has' : 'have'} a shortfall and ${fundedN} ${fundedN === 1 ? 'is' : 'are'} well funded.` +
    (shortN
      ? ' Revise any goal or need with a shortfall, or close it on Build my plan by taking a protection product or an investing plan.'
      : '');
  const ratiosTip =
    badRatios === 0
      ? `All ${R.length} ratios are in good shape.`
      : `Financial health ratios: ${ratioStatus}.`;
  const riskTip = `The plan uses ${suitable.label} (${suitable.volLabel} annual volatility) — the lower of risk ability and risk tolerance.`;

  useEffect(() => {
    const next = capEnabledNeeds(session.needs.map(n => ({ ...n, gap: needCardGap(session, n) })));
    const changed = next.some(n => session.needs.find(x => x.type === n.type)?.enabled !== n.enabled);
    if (changed) onChange({ needs: next });
  }, [session.needs, onChange]);

  useEffect(() => {
    if (!editNeed) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeModal();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [editNeed]);

  const openNeed = (t: NeedType) => {
    const { needs, extra } = applyNeedPatch(session, t, {});
    onChange({ needs, ...extra });
    setEditNeed(t);
  };

  return (
    <>
      <div className="x-h1" style={{ marginBottom: 20 }}>
        Your HappiU, and the goals and needs people like {who} typically have
      </div>

      <div className="x-card x-pad x-fade" style={{ padding: 30 }}>
        <div className="x-score">
          <div className="x-score-viz">
            <p className="x-sm" style={{ textAlign: 'center', margin: '0 0 14px', maxWidth: '28ch' }}>
              One number for how well your money holds up.
            </p>
            {busy && pre == null ? (
              <div className="x-sm">Working out your HappiU Score…</div>
            ) : scoreError && pre == null ? (
              <div className="x-sm">{scoreError}</div>
            ) : (
              <>
                <div ref={scoreRef} className="x-score-ghit">
                  <HappiUGauge value={score} size={258} showBand={false} />
                </div>
                <p className="x-scorecap" style={{ color: HAPPI_COL[band] }}>
                  {read}
                </p>
              </>
            )}
            <NarrBtn
              ariaLabel="Explain your HappiU score"
              label="Explain your HappiU score"
              on={narrKind === 'score'}
              paused={narrPaused}
              onClick={() => onNarr('score')}
            />
          </div>
          <div className="x-score-goals">
            <p className="x-sm" style={{ margin: '0 0 14px' }}>
              The goals and needs people like {who} typically have, and the gaps between what you hold today and what
              each one needs.
            </p>
            <div className="x-score-tags">
              <div ref={needsRef} className="x-need-rows">
                {chipNeeds.map(g => (
                  <button
                    key={g.type}
                    className={`x-chip ${g.gap > 0 ? 'no' : 'ok'}`}
                    type="button"
                    onClick={() => openNeed(g.type)}
                  >
                    <span>
                      {NEED_META[g.type].label}: {g.gap > 0 ? `Shortfall ${moneyK(g.gap)}` : 'Fully funded'}
                    </span>
                    {Ico.pencil}
                  </button>
                ))}
              </div>
            </div>
            <NarrBtn
              ariaLabel="Explain your goals and needs"
              label="Explain your goals and needs"
              on={narrKind === 'needs'}
              paused={narrPaused}
              onClick={() => onNarr('needs')}
            />
          </div>
        </div>
      </div>

      <div className="x-sec">
        <div className={`x-needs${needsOpen ? ' open' : ''}`}>
          <button
            className="x-needsh"
            type="button"
            aria-expanded={needsOpen}
            onClick={() => setNeedsOpen(open => !open)}
          >
            <b>Where you should set the focus</b>
            <GroupTag session={session} keys={[]} verb="have these goals" />
            <span className="cv">{Ico.chev}</span>
          </button>
          {needsOpen ? (
            <>
              <NeedGroups session={session} onChange={onChange} onToggleNeed={onToggleNeed} />
              {offNeeds.length || offExtra.length ? (
                <div className="x-add">
                  <span className="x-sm">Also worth looking at</span>
                  {offNeeds.map(n => (
                    <button key={n.type} className="x-btn sm" type="button" onClick={() => onToggleNeed(n.type)}>
                      + {NEED_META[n.type].label}
                    </button>
                  ))}
                  {offExtra.map(x => (
                    <button key={x.k} className="x-btn sm" type="button" onClick={() => onToggleExtra(x.k)}>
                      + {x.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      </div>

      <div className="x-sec">
        <div id="x-risk" className={`x-needs${riskOpen ? ' open' : ''}`}>
          <button
            ref={riskRef}
            className="x-needsh"
            type="button"
            aria-expanded={riskOpen}
            onClick={() => setRiskOpen(open => !open)}
          >
            <b>How much market risk this plan should take</b>
            <span className={`x-chip ${suitable.chipClass}`}>{riskChip}</span>
            <span className="cv">{Ico.chev}</span>
          </button>
          {riskOpen ? (
            <>
              <p className="x-sm" style={{ margin: '0 0 16px' }}>
                How much market swing your balance sheet can carry, and how much you say you can sit with. The plan
                uses the lower of the two.{' '}
                <InfoTip className="x-r-info" text={RISK_ABILITY_TIP} label="how much market risk this plan should take" wide />
              </p>
              <div className="x-risk">
                <div className="x-risk-cap">
                  <div className="x-r-h">
                    <b>Risk ability</b>
                    <span className={`x-chip ${ability.chipClass}`}>{ability.label}</span>
                  </div>
                  <p>
                    Calculated from cash cover, debt, the share of income you save, years to retirement, and
                    dependants. Raise it by changing those figures on Your money.
                  </p>
                  <RiskBandTrack value={cap.capacity} readOnly ariaLabel="Risk ability" />
                  {cap.capReason ? <div className="rec">{cap.capReason}</div> : null}
                </div>
                <div className="x-risk-tol">
                  <div className="x-r-h">
                    <b>Risk tolerance</b>
                    <span className={`x-chip ${comfort.chipClass}`}>{comfort.label}</span>
                  </div>
                  <p>
                    How much your investments can rise and fall before you would want to sell. Drag the slider to
                    set this — it is the one you can change.
                  </p>
                  <RiskBandTrack
                    value={tolerance}
                    onChange={v => onChange({ riskTolerance: v, riskToleranceTouched: true })}
                    ariaLabel="Risk tolerance"
                  />
                </div>
              </div>
              {tolerance > cap.capacity ? (
                <p className="x-note" style={{ marginTop: 14 }}>
                  Your comfort is above what your balance sheet can carry. The plan uses risk ability
                  ({ability.label}) as the cap.
                </p>
              ) : null}
            </>
          ) : null}
        </div>
      </div>

      <div className="x-sec">
        <div id="x-money-health" className={`x-needs${healthOpen ? ' open' : ''}`}>
          <button
            ref={ratiosRef}
            className="x-needsh"
            type="button"
            aria-expanded={healthOpen}
            onClick={() => setHealthOpen(open => !open)}
          >
            <b>Your financial health ratios</b>
            <span className={`x-chip ${ratioTone}`}>{ratioStatus}</span>
            <span className="cv">{Ico.chev}</span>
          </button>
          {healthOpen ? (
            <>
              <p className="x-sm" style={{ margin: '0 0 16px' }}>
                Six checks on the figures you gave us, read against the recommended bands.
              </p>
              <div className="x-rat">
                {R.map(r => (
                  <RatioCard key={r.k} r={r} />
                ))}
              </div>
            </>
          ) : null}
        </div>
      </div>

      {editNeed ? (
        <div className="x-modal" role="dialog" aria-modal="true" aria-label={NEED_META[editNeed].label}>
          <div className="x-modal-bd" onClick={closeModal} />
          <div className="x-modal-w x-modal-gc">
            <button className="x-modal-x" type="button" aria-label="Close" onClick={closeModal}>
              {Ico.close}
            </button>
            <GoalCard
              session={session}
              type={editNeed}
              startOpen
              onToggle={() => onToggleNeed(editNeed)}
              onChange={onChange}
            />
          </div>
        </div>
      ) : null}

      <CoachTour
        enabled={gtTtOn && scoreReady}
        onComplete={onGtTtComplete}
        steps={[
          {
            title: 'Your HappiU score',
            body: scoreTip,
            anchorRef: scoreRef,
          },
          {
            title: 'Goals and needs',
            body: needsTip,
            anchorRef: needsRef,
          },
          {
            title: 'How much market risk this plan should take',
            body: riskTip,
            anchorRef: riskRef,
          },
          {
            title: 'Money-health ratios',
            body: ratiosTip,
            anchorRef: ratiosRef,
          },
        ]}
      />

      <Foot>
        <button className="x-btn g" type="button" onClick={onBack}>
          ← Back
        </button>
        <span className="sp" />
        <button className="x-btn p" type="button" onClick={() => onPlan()} disabled={busy}>
          {busy ? 'Projecting…' : 'Build my plan →'}
        </button>
      </Foot>
    </>
  );
}

function RiskBandTrack({
  value,
  onChange,
  readOnly = false,
  ariaLabel,
}: {
  value: number;
  onChange?: (profile: number) => void;
  readOnly?: boolean;
  ariaLabel: string;
}) {
  const profile = clampRiskProfile(value);
  const selected = riskLevel(profile);
  const markLeft = `${((profile - 0.5) / 5) * 100}%`;
  return (
    <div
      className={`x-risk-slider${readOnly ? ' ro' : ''}`}
      style={{ ['--risk-accent' as string]: selected.accent, ['--risk-track' as string]: RISK_TRACK_GRADIENT }}
    >
      {readOnly ? (
        <div
          className="x-risk-rail"
          role="img"
          aria-label={`${ariaLabel}: ${selected.label}, annual volatility ${selected.volLabel}`}
        >
          <i className="x-risk-mark" style={{ left: markLeft }} />
        </div>
      ) : (
        <input
          type="range"
          min={1}
          max={5}
          step={1}
          value={profile}
          aria-label={ariaLabel}
          aria-valuetext={`${selected.label}, annual volatility ${selected.volLabel}`}
          onChange={e => onChange?.(Number(e.target.value))}
        />
      )}
      <div className="x-risk-labs">
        {RISK_LEVELS.map(level => {
          const on = level.profile === profile;
          if (readOnly || !onChange) {
            return (
              <span key={level.profile} className={on ? 'on' : ''}>
                {level.label}
              </span>
            );
          }
          return (
            <button
              key={level.profile}
              type="button"
              className={on ? 'on' : ''}
              onClick={() => onChange(level.profile)}
            >
              {level.label}
            </button>
          );
        })}
      </div>
      <p className="x-sm" style={{ margin: '8px 0 0' }}>
        Annual volatility {selected.volLabel}
      </p>
      <p className="x-risk-edit">{readOnly ? '\u00a0' : 'Drag to set'}</p>
    </div>
  );
}

function RatioCard({ r, showWhy }: { r: Ratio; showWhy?: boolean }) {
  const why = X_RATIO_WHY[r.k];
  return (
    <div className={`x-r ${r.ok ? 'ok' : 'no'}${showWhy ? ' open' : ''}`}>
      <div className="x-r-h">
        <b>
          {r.n}
          {why ? <InfoTip className="x-r-info" text={`${why[0]} ${why[1]}`} /> : null}
        </b>
        <span className="x-face">{r.ok ? Ico.thumbUp : Ico.thumbDn}</span>
      </div>
      <div className="x-r-v">
        <b>{rnum(r.v)}</b>
        <span>{r.unit}</span>
      </div>
      <p>{r.ok ? r.good : r.bad}</p>
      <div className="rec">Recommended {r.rec}</div>
      {showWhy && why ? (
        <div className="x-r-why">
          <p>{why[0]}</p>
          <div className="f">{why[1]}</div>
        </div>
      ) : null}
    </div>
  );
}
