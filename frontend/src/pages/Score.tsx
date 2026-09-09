import { useEffect, useRef, useState } from 'react';
import { CoachTour } from '../components/CoachTour';
import { HappiUGauge } from '../components/HappiUGauge';
import { GoalCard, NeedGroups } from '../components/GoalCard';
import { Foot, GroupTag, NarrBtn } from '../components/ui';
import { X_RATIO_WHY } from '../lib/catalog';
import { Ico } from '../lib/icons';
import { applyNeedPatch, needCardGap } from '../lib/needEdit';
import { moneyRatios, rnum, type Ratio } from '../lib/ratios';
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
  narrOn,
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
  narrOn: boolean;
  onNarr: () => void;
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
  const ratioShape = `${okRatios} out of ${R.length} ratios ${okRatios === 1 ? 'is' : 'are'} in good shape`;
  const ratioOk = okRatios === R.length;
  const [needsOpen, setNeedsOpen] = useState(false);
  const [healthOpen, setHealthOpen] = useState(false);
  const [editNeed, setEditNeed] = useState<NeedType | null>(null);
  const scoreRef = useRef<HTMLDivElement>(null);
  const needsRef = useRef<HTMLDivElement>(null);
  const ratiosRef = useRef<HTMLSpanElement>(null);
  const closeModal = () => setEditNeed(null);
  const who = firstName(session);
  const shortN = taggedNeeds.filter(n => n.gap > 0).length;
  const fundedN = taggedNeeds.length - shortN;
  const badRatios = R.length - okRatios;
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
    `${okRatios} of ${R.length} ratios ${okRatios === 1 ? 'is' : 'are'} in good shape. ` +
    `${badRatios} of ${R.length} ${badRatios === 1 ? 'is' : 'are'} not. Click the icon to open the checks.`;

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

  const openHealth = () => {
    setHealthOpen(true);
    window.requestAnimationFrame(() => {
      document.getElementById('x-money-health')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  return (
    <>
      <div className="x-h1">Your financial future</div>
      <div className="x-lead" style={{ maxWidth: 'none', marginBottom: 20 }}>
        HappiU, the one financial wellbeing number for how well what you hold today covers what your life actually needs. It moves as you close gaps.
      </div>

      <div className="x-card x-pad x-fade" style={{ padding: 30 }}>
        <div className="x-score">
          <div className="x-score-viz">
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
            <div className="x-score-narr">
              <NarrBtn ariaLabel="Explain your HappiU score" label="Explain your HappiU score" on={narrOn} onClick={onNarr} />
            </div>
          </div>
          <div>
            <div className="x-scoreh">
              <div className="x-h2">How well will your finances hold up?</div>
              <p className="x-sm" style={{ marginTop: 6, maxWidth: '46ch' }}>
                HappiU gives you one simple score for the resilience of your money against whatever comes next.
              </p>
            </div>
            <div className="x-score-tags">
              <div ref={needsRef} className="x-need-rows">
                {taggedNeeds.map(g => (
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
              <button
                className={`x-chip ${ratioOk ? 'ok' : 'no'}`}
                type="button"
                onClick={openHealth}
              >
                <span>{ratioShape}</span>
                <span ref={ratiosRef} className="x-coach-hit">
                  {Ico.eye}
                </span>
              </button>
            </div>
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
        <div id="x-money-health" className={`x-needs${healthOpen ? ' open' : ''}`}>
          <button
            className="x-needsh"
            type="button"
            aria-expanded={healthOpen}
            onClick={() => setHealthOpen(open => !open)}
          >
            <b>Your financial health ratios</b>
            <span className={`x-chip ${ratioOk ? 'ok' : 'no'}`}>{ratioShape}</span>
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

function RatioCard({ r, showWhy }: { r: Ratio; showWhy?: boolean }) {
  const why = X_RATIO_WHY[r.k];
  return (
    <div className={`x-r ${r.ok ? 'ok' : 'no'}${showWhy ? ' open' : ''}`}>
      <div className="x-r-h">
        <b>{r.n}</b>
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
