import { useEffect, useRef, useState } from 'react';
import { CoachTour } from '../components/CoachTour';
import { InfoTip } from '../components/InfoTip';
import { PLOT_MARGIN } from '../components/Plot';
import { SvBusy } from '../components/SvBusy';
import { SvChart } from '../components/SvChart';
import { Foot, NarrBtn } from '../components/ui';
import { assumeChangedCount } from '../lib/assumptions';
import type { ChartMarker } from '../lib/chartMarkers';
import type { ExplainKind } from '../lib/explain';
import { Ico } from '../lib/icons';
import { PLAN_FOR_NEED, planRemain, suggestedNeeds } from '../lib/planProducts';
import { chartCopy, pickEarmarked, type ChartView, type SvData } from '../lib/sv';
import {
  firstName,
  isNeedType,
  moneyK,
  NEED_META,
  sessionAge,
  type ExtraNeed,
  type GpSession,
  type NeedType,
} from '../lib/types';
import { PlanModals } from './plan/PlanModals';
import { PlanReport } from './plan/PlanReport';
import { ReportNotify } from './plan/ReportNotify';
import { SuggestedPlan } from './plan/SuggestedPlan';

function listAnd(names: string[]): string {
  if (!names.length) return '';
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

const CHART_VIEWS: { id: ChartView; label: string }[] = [
  { id: 'wealth', label: 'Net Wealth' },
  { id: 'cash', label: 'Cashflow' },
  { id: 'exp', label: 'Expense Funding' },
  { id: 'sav', label: 'Savings' },
];

export function Plan({
  session,
  pre,
  post,
  svData,
  projectError,
  onChange,
  onBack,
  onToggleNeed,
  onToggleExtra,
  onToggleEvent,
  onAssume,
  onAssumeReset,
  onMarkerMove,
  onMarkerClick,
  busy,
  narrKind,
  onNarr,
  onToast,
  reportOpen,
  onReportOpenChange,
  shareOpen,
  onShareOpenChange,
  gtTtOn,
  onGtTtComplete,
}: {
  session: GpSession;
  pre: number | null;
  post: number | null;
  svData: SvData | null;
  projectError: string | null;
  onChange: (p: Partial<GpSession>) => void;
  onBack: () => void;
  onToggleNeed: (t: NeedType) => void;
  onToggleExtra: (k: ExtraNeed) => void;
  onToggleEvent: (id: string) => void;
  onAssume: (p: Partial<GpSession>) => void;
  onAssumeReset: () => void;
  onMarkerMove: (marker: ChartMarker, newX: number) => void;
  onMarkerClick: (marker: ChartMarker) => void;
  busy: boolean;
  narrKind: string | null;
  onNarr: (kind: ExplainKind, extras?: { chartView?: ChartView }) => void;
  onToast?: (msg: string) => void;
  reportOpen: boolean;
  onReportOpenChange: (open: boolean) => void;
  shareOpen: boolean;
  onShareOpenChange: (open: boolean) => void;
  gtTtOn: boolean;
  onGtTtComplete: () => void;
}) {
  const [view, setView] = useState<ChartView>('wealth');
  const [moreOpen, setMoreOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(
    () => !gtTtOn && (session.tip?.startsWith('panel-plans') ?? false),
  );
  const [editProd, setEditProd] = useState<NeedType | null>('N_RET');
  const [planModal, setPlanModal] = useState<NeedType | null>(null);
  const moreRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const mixRef = useRef<HTMLDivElement>(null);
  const gapRef = useRef<HTMLButtonElement>(null);
  const end = session.endAge || 85;
  const score = post ?? pre ?? 0;
  const panel = session.tip?.startsWith('panel-goals')
    ? 'goals'
    : session.tip?.startsWith('panel-events')
      ? 'events'
      : session.tip?.startsWith('panel-assume')
        ? 'assume'
        : session.tip?.startsWith('panel-plans')
          ? 'plans'
          : null;
  const focusId = session.tip?.includes(':') ? session.tip.split(':')[1] : null;
  const planNeed = panel === 'plans' && isNeedType(focusId) ? focusId : null;
  const nAssume = assumeChangedCount(session);
  const earmarked = svData ? pickEarmarked(svData, 'pre') : null;
  const copy = chartCopy(view, !!earmarked);
  const viewLabel = CHART_VIEWS.find(v => v.id === view)?.label ?? 'Net Wealth';
  const otherViews = CHART_VIEWS.filter(v => v.id !== view);
  const who = firstName(session);
  const age = sessionAge(session) || 40;
  const hasRet = session.needs.some(n => n.type === 'N_RET' && n.enabled);
  const retNeed = session.needs.find(n => n.type === 'N_RET' && n.enabled);
  const retAge = retNeed?.retAge || session.ageOfRetirement || 65;
  const planItems = suggestedNeeds(session).map(n => ({
    type: n.type,
    title: PLAN_FOR_NEED[n.type],
    remain: planRemain(session, n.type),
  }));
  const fundedItems = planItems.filter(i => i.remain <= 0);
  const shortItems = [...planItems.filter(i => i.remain > 0)].sort((a, b) => b.remain - a.remain);
  const worst = shortItems[0] ?? null;
  const chartReady = svData != null || !!projectError;
  const lead = who === 'you' ? 'This is' : `${who}, this is`;
  const drag = hasRet
    ? ` Retirement sits at ${retAge} — drag that marker to try a later or earlier date.`
    : ' Drag a goal marker on the timeline to change the year.';
  const chartTip = `${lead} available assets from age ${age} to ${end}.${drag} The line is this plan, not a forecast you cannot change.`;
  let mixTip = `People like ${who} usually consider a mix of protection and investing. Every activated goal is already funded.`;
  if (planItems.length) {
    mixTip = `People like ${who} usually close these with ${listAnd(planItems.map(i => i.title))}.`;
    if (fundedItems.length && shortItems.length) {
      mixTip += ` ${listAnd(fundedItems.map(i => i.title))} ${fundedItems.length === 1 ? 'is' : 'are'} funded. ${worst?.title} still has a ${moneyK(worst.remain)} shortfall.`;
    } else if (shortItems.length && worst) {
      mixTip += ` None are fully funded yet. ${worst.title} still has a ${moneyK(worst.remain)} shortfall.`;
    } else {
      mixTip += ' All of these are funded.';
    }
  }
  const preN = pre == null ? null : Math.round(pre);
  const postN = post == null ? null : Math.round(post);
  let happiBit = '';
  if (preN != null && postN != null && postN !== preN) happiBit = ` HappiU moves from ${preN} to ${postN} as you do.`;
  else if (postN != null) happiBit = ` HappiU with this plan is ${postN}.`;
  else if (preN != null) happiBit = ` HappiU today is ${preN}.`;
  const kind = worst && NEED_META[worst.type].group === 'p' ? 'a protection product' : 'an investing plan';
  const gapTip = worst
    ? `${worst.title} is the gap left to close. Tap the pencil to size ${kind}.${happiBit}`
    : 'All suggested items are funded — open a chip to change the mix.';

  useEffect(() => {
    if (!moreOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!moreRef.current?.contains(e.target as Node)) setMoreOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [moreOpen]);

  useEffect(() => {
    if (session.tip?.startsWith('panel-plans') && !gtTtOn) setPlanOpen(true);
  }, [session.tip, gtTtOn]);

  useEffect(() => {
    if (!gtTtOn) return;
    setView('wealth');
    setPlanOpen(false);
    setPlanModal(null);
  }, [gtTtOn]);

  return (
    <>
      <div className="x-h1" style={{ whiteSpace: 'nowrap' }}>
        See what this plan does
      </div>
      <div className="x-lead" style={{ maxWidth: 'none', marginBottom: 20 }}>
        The chart is your financial future projected to age {end}. Apply a what-if like a market crash or six months out
        of work, and watch the line change. Click a goal icon on the timeline to open that plan.
      </div>

      <div
        className="x-card x-fade"
        style={{
          overflow: 'visible',
          ['--plot-ml' as string]: `${PLOT_MARGIN.l}px`,
          ['--plot-mr' as string]: `${PLOT_MARGIN.r}px`,
        }}
      >
        <div className="x-svhead">
          <b className="x-svtitle">
            {copy.title}
            <InfoTip text={copy.info} />
          </b>
          <span className="x-addbs">
            <button className="x-addb" type="button" onClick={() => onChange({ tip: 'panel-events' })}>
              + Stress Test
            </button>
          </span>
          <span className="x-svhead-sp" />
          <span className="chip on">{viewLabel}</span>
          <div className="x-svdd" ref={moreRef}>
            <button
              className="chip"
              type="button"
              aria-expanded={moreOpen}
              aria-haspopup="listbox"
              onClick={() => setMoreOpen(open => !open)}
            >
              More…
            </button>
            {moreOpen ? (
              <ul className="x-svdd-menu" role="listbox" aria-label="Chart view">
                {otherViews.map(v => (
                  <li key={v.id}>
                    <button
                      type="button"
                      role="option"
                      onClick={() => {
                        setView(v.id);
                        setMoreOpen(false);
                      }}
                    >
                      {v.label}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          {busy ? <SvBusy compact /> : null}
          <NarrBtn label="Explain this chart" on={narrKind === 'chart'} onClick={() => onNarr('chart', { chartView: view })} />
        </div>
        <div ref={chartRef} className="x-svplot-wrap" aria-busy={busy}>
        <SvChart
          data={svData}
          view={view}
          session={session}
          busy={busy}
          error={projectError}
          onMarkerMove={onMarkerMove}
          onMarkerClick={marker => {
            if (marker.kind === 'event') {
              onMarkerClick(marker);
              return;
            }
            if (marker.kind !== 'need') return;
            const id = marker.id === 'retirement' ? 'N_RET' : marker.id;
            if (isNeedType(id) && session.needs.some(n => n.type === id && n.enabled)) {
              setPlanModal(id);
            }
          }}
        />
        {busy ? (
          <div className="x-svplot-busy">
            <SvBusy />
          </div>
        ) : null}
        </div>
      </div>

      <SuggestedPlan
        session={session}
        score={score}
        planOpen={planOpen}
        setPlanOpen={setPlanOpen}
        editProd={editProd}
        setEditProd={setEditProd}
        planModal={planModal}
        setPlanModal={setPlanModal}
        onChange={onChange}
        onToggleExtra={onToggleExtra}
        narrKind={narrKind}
        onNarr={onNarr}
        mixRef={mixRef}
        gapRef={gapRef}
        gapType={worst?.type ?? null}
      />

      <PlanModals
        panel={panel}
        focusId={focusId}
        planNeed={planNeed}
        session={session}
        nAssume={nAssume}
        onChange={onChange}
        onToggleNeed={onToggleNeed}
        onToggleExtra={onToggleExtra}
        onToggleEvent={onToggleEvent}
        onAssume={onAssume}
        onAssumeReset={onAssumeReset}
      />

      {reportOpen ? (
        <PlanReport
          session={session}
          pre={pre}
          post={post}
          svData={svData}
          onClose={() => onReportOpenChange(false)}
          onChange={onChange}
        />
      ) : null}

      {shareOpen ? (
        <ReportNotify
          session={session}
          pre={pre}
          post={post}
          onClose={() => onShareOpenChange(false)}
          onToast={onToast || (() => undefined)}
          onShared={p =>
            onChange({
              reportMobile: p.mobile,
              reportEmail: p.email,
              reportJobId: p.jobId,
              reportMediaUrl: '',
              reportVideoStatus: 'pending',
            })
          }
        />
      ) : null}

      <CoachTour
        enabled={gtTtOn && chartReady && !planOpen && !reportOpen && !shareOpen}
        onComplete={onGtTtComplete}
        steps={[
          {
            title: 'Projected assets',
            body: chartTip,
            anchorRef: chartRef,
          },
          {
            title: 'Suggested plan',
            body: mixTip,
            anchorRef: mixRef,
          },
          {
            title: worst ? worst.title : 'Suggested plan',
            body: gapTip,
            anchorRef: worst ? gapRef : mixRef,
          },
        ]}
      />

      <Foot>
        <button className="x-btn g" type="button" onClick={onBack}>
          ← Back
        </button>
        <span className="sp" />
        <button className="x-assumb" type="button" onClick={() => onReportOpenChange(true)}>
          {Ico.eye}View report
        </button>
        <button className="x-assumb" type="button" onClick={() => onShareOpenChange(true)}>
          {Ico.share}Share report
        </button>
        <button className="x-assumb" type="button" onClick={() => onChange({ tip: 'panel-assume' })}>
          {Ico.sliders}Assumptions{nAssume ? <em className="x-assn">{nAssume}</em> : null}
        </button>
      </Foot>
    </>
  );
}
