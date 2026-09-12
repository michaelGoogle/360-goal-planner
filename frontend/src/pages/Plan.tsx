import { useEffect, useRef, useState } from 'react';
import { CoachTour } from '../components/CoachTour';
import { InfoTip } from '../components/InfoTip';
import { PLOT_MARGIN } from '../components/Plot';
import { SvBusy } from '../components/SvBusy';
import { SvChart } from '../components/SvChart';
import { Foot, NarrBtn } from '../components/ui';
import type { ChartMarker } from '../lib/chartMarkers';
import type { ExplainKind } from '../lib/explain';
import { Ico } from '../lib/icons';
import { postJson, sessionPayload } from '../lib/api';
import { loadAuthSession } from '../lib/auth';
import { anyPlanOn, PLAN_FOR_NEED, planRemain, suggestedNeeds } from '../lib/planProducts';
import { chartCopy, pickEarmarked, type ChartView, type SvData } from '../lib/sv';
import {
  firstName,
  isNeedType,
  moneyK,
  NEED_META,
  sessionAge,
  type ExtraNeed,
  type GpEvent,
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

type PlanTourItem = { type: NeedType; title: string; remain: number; group: 'p' | 'w' };

function shortWithAmount(items: PlanTourItem[]): string {
  return listAnd(items.map(i => `${i.title} (${moneyK(i.remain)})`));
}

function suggestedPlanTourBody(who: string, items: PlanTourItem[]): string {
  if (!items.length) {
    return `People like ${who} usually close Wealth protection first, then invest leftover budget in Wealth growth. Every activated goal is already funded.`;
  }
  const protectShort = items.filter(i => i.group === 'p' && i.remain > 0).sort((a, b) => b.remain - a.remain);
  const growthShort = items.filter(i => i.group === 'w' && i.remain > 0).sort((a, b) => b.remain - a.remain);
  const protectFunded = items.some(i => i.group === 'p' && i.remain <= 0);

  if (!protectShort.length && !growthShort.length) {
    return `People like ${who} usually close Wealth protection first, then invest leftover budget in Wealth growth. All of these are funded.`;
  }
  if (protectShort.length) {
    let text = `Close the Wealth protection shortfall first — ${shortWithAmount(protectShort)}.`;
    if (growthShort.length) {
      text += ` Then invest the remaining budget in Wealth growth — ${listAnd(growthShort.map(i => i.title))}.`;
    }
    return text;
  }
  if (protectFunded) {
    return `Wealth protection is already funded. Put the remaining budget into Wealth growth — ${shortWithAmount(growthShort)}.`;
  }
  return `Put the remaining budget into Wealth growth — ${shortWithAmount(growthShort)}.`;
}

const CHART_VIEWS: { id: ChartView; label: string }[] = [
  { id: 'wealth', label: 'Net Wealth' },
  { id: 'cash', label: 'Cashflow' },
  { id: 'exp', label: 'Expense Funding' },
];

export function Plan({
  session,
  pre,
  post,
  svData,
  svPayload,
  projectError,
  onChange,
  onBack,
  onToggleNeed,
  onToggleExtra,
  onToggleEvent,
  onEvents,
  onMarkerMove,
  onMarkerClick,
  busy,
  narrKind,
  narrPaused,
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
  svPayload: Record<string, unknown> | null;
  projectError: string | null;
  onChange: (p: Partial<GpSession>) => void;
  onBack: () => void;
  onToggleNeed: (t: NeedType) => void;
  onToggleExtra: (k: ExtraNeed) => void;
  onToggleEvent: (id: string) => void;
  onEvents: (events: GpEvent[]) => void;
  onMarkerMove: (marker: ChartMarker, newX: number) => void;
  onMarkerClick: (marker: ChartMarker) => void;
  busy: boolean;
  narrKind: string | null;
  narrPaused?: boolean;
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
  const [svOpen, setSvOpen] = useState(false);
  const [svInspect, setSvInspect] = useState<{
    gp: Record<string, unknown>;
    sv: Record<string, unknown> | null;
    error: string | null;
    loading: boolean;
  } | null>(null);
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
      : session.tip?.startsWith('panel-plans')
        ? 'plans'
        : null;
  const focusId = session.tip?.includes(':') ? session.tip.split(':')[1] : null;
  const planNeed = panel === 'plans' && isNeedType(focusId) ? focusId : null;
  const plansOn = anyPlanOn(session);
  const earmarked = svData ? pickEarmarked(svData, 'post') || pickEarmarked(svData, 'pre') : null;
  const copy = chartCopy(view, !!earmarked, plansOn);
  const viewLabel = CHART_VIEWS.find(v => v.id === view)?.label ?? 'Net Wealth';
  const leadText =
    view === 'cash'
      ? `Money in and out each year to age ${end}. Apply this plan to include its premiums and payouts, or turn it off to go without.`
      : view === 'exp'
        ? `What pays for spending each year to age ${end}. Apply this plan to see if the mix closes more of the gap, or turn it off to go without.`
        : `Compare the recommended plan (solid) with going without it (dotted). Stress-test a shock or drag a goal to see if the benefit still holds to age ${end}.`;
  const otherViews = CHART_VIEWS.filter(v => v.id !== view);
  const who = firstName(session);
  const age = sessionAge(session) || 40;
  const hasRet = session.needs.some(n => n.type === 'N_RET' && n.enabled);
  const retNeed = session.needs.find(n => n.type === 'N_RET' && n.enabled);
  const retAge = retNeed?.retAge || session.ageOfRetirement || 65;
  const planItems: PlanTourItem[] = suggestedNeeds(session).map(n => ({
    type: n.type,
    title: PLAN_FOR_NEED[n.type],
    remain: planRemain(session, n.type),
    group: NEED_META[n.type].group,
  }));
  const protectShort = [...planItems.filter(i => i.group === 'p' && i.remain > 0)].sort((a, b) => b.remain - a.remain);
  const growthShort = [...planItems.filter(i => i.group === 'w' && i.remain > 0)].sort((a, b) => b.remain - a.remain);
  const focus = protectShort[0] ?? growthShort[0] ?? null;
  const chartReady = svData != null || !!projectError;
  const lead = who === 'you' ? 'This is' : `${who}, this is`;
  const drag = hasRet
    ? ` Retirement sits at ${retAge} — drag that marker to try a later or earlier date.`
    : ' Drag a goal marker on the timeline to change the year.';
  const chartTip = `${lead} available assets from age ${age} to ${end}. The solid line is this plan; the dotted line is without it.${drag} Not a forecast you cannot change.`;
  const mixTip = suggestedPlanTourBody(who, planItems);
  const preN = pre == null ? null : Math.round(pre);
  const postN = post == null ? null : Math.round(post);
  let happiBit = '';
  if (preN != null && postN != null && postN !== preN) happiBit = ` HappiU moves from ${preN} to ${postN} as you do.`;
  else if (postN != null) happiBit = ` HappiU with this plan is ${postN}.`;
  else if (preN != null) happiBit = ` HappiU today is ${preN}.`;
  const kind = focus && focus.group === 'p' ? 'a protection product' : 'an investing plan';
  const gapTip = focus
    ? `${focus.title} is the gap left to close. Tap the pencil to size ${kind}.${happiBit}`
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

  useEffect(() => {
    if (!svOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSvOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [svOpen]);

  useEffect(() => {
    if (!svOpen) return;
    const ac = new AbortController();
    const gp = sessionPayload(session) as Record<string, unknown>;
    setSvInspect({ gp, sv: svPayload, error: null, loading: true });
    void postJson<{ success: boolean; payload?: Record<string, unknown> }>(
      '/v1/sv-payload',
      gp,
      loadAuthSession()?.access_token,
      ac.signal,
    )
      .then(res => {
        if (ac.signal.aborted) return;
        const mapped = res.payload && typeof res.payload === 'object' ? res.payload : null;
        setSvInspect({ gp, sv: mapped ?? svPayload, error: null, loading: false });
      })
      .catch(err => {
        if (ac.signal.aborted || (err instanceof Error && err.name === 'AbortError')) return;
        setSvInspect({
          gp,
          sv: svPayload,
          error: err instanceof Error ? err.message : 'Could not map the SV body. Restart the GP server on port 8009.',
          loading: false,
        });
      });
    return () => ac.abort();
  }, [svOpen, session, svPayload]);

  return (
    <>
      <div className="x-h1" style={{ whiteSpace: 'nowrap' }}>
        See the benefit of this plan
      </div>
      <div className="x-lead" style={{ marginBottom: 20 }}>
        {leadText}
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
            <span>{copy.title}</span>
            <InfoTip text={copy.info} />
          </b>
          {view === 'wealth' && plansOn ? null : (
            <span className="x-svside">{plansOn ? 'With this plan' : 'Without this plan'}</span>
          )}
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
          <div className="x-svhead-end">
            <NarrBtn label="Explain this chart" on={narrKind === 'chart'} paused={narrPaused} onClick={() => onNarr('chart', { chartView: view })} />
            <button
              className="x-svdbg"
              type="button"
              aria-label="Show Scenario Visualizer payload"
              onClick={() => setSvOpen(true)}
            />
          </div>
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

      {svOpen ? (
        <div className="x-modal" role="dialog" aria-modal="true" aria-label="Scenario Visualizer payload">
          <div className="x-modal-bd" onClick={() => setSvOpen(false)} />
          <div className="x-modal-w x-modal-sv">
            <div className="x-modal-h">
              <div className="t">
                <b>SV request</b>
                <span>
                  {svInspect?.loading
                    ? 'Mapping the current session…'
                    : svInspect?.sv?.benefitVisualizerOutput
                      ? `benefitVisualizerOutput has ${Array.isArray(svInspect.sv.benefitVisualizerOutput) ? svInspect.sv.benefitVisualizerOutput.length : 0} product(s).`
                      : svInspect?.error
                        ? svInspect.error
                        : 'No benefitVisualizerOutput — post path matches pre.'}
                </span>
              </div>
              <button
                className="x-assumb"
                type="button"
                onClick={() => {
                  const shown = svInspect?.sv ?? svInspect?.gp ?? null;
                  const text = shown ? JSON.stringify(shown, null, 2) : 'null';
                  void navigator.clipboard?.writeText(text).then(
                    () => onToast?.('SV payload copied'),
                    () => onToast?.('Could not copy'),
                  );
                }}
              >
                Copy
              </button>
              <button className="x-modal-x" type="button" aria-label="Close" onClick={() => setSvOpen(false)}>
                {Ico.close}
              </button>
            </div>
            <div className="x-modal-b">
              <pre className="x-svpayload">
                {svInspect?.loading
                  ? 'Mapping…'
                  : JSON.stringify(
                      {
                        mappedSvBody: svInspect?.sv ?? null,
                        gpSessionSent: svInspect?.gp ?? null,
                        error: svInspect?.error ?? null,
                      },
                      null,
                      2,
                    )}
              </pre>
            </div>
          </div>
        </div>
      ) : null}

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
        narrPaused={narrPaused}
        onNarr={onNarr}
        mixRef={mixRef}
        gapRef={gapRef}
        gapType={focus?.type ?? null}
      />

      <PlanModals
        panel={panel}
        focusId={focusId}
        planNeed={planNeed}
        session={session}
        onChange={onChange}
        onToggleNeed={onToggleNeed}
        onToggleExtra={onToggleExtra}
        onToggleEvent={onToggleEvent}
        onEvents={onEvents}
      />

      {reportOpen ? (
        <PlanReport
          session={session}
          pre={pre}
          post={post}
          svData={svData}
          onClose={() => onReportOpenChange(false)}
          onShare={() => onShareOpenChange(true)}
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
            title: focus ? focus.title : 'Suggested plan',
            body: gapTip,
            anchorRef: focus ? gapRef : mixRef,
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
      </Foot>
    </>
  );
}
