import { useCallback, useEffect, useRef, useState } from 'react';
import { Shell } from './components/Shell';
import { AssumeModal } from './components/AssumeModal';
import { Intro } from './pages/Intro';
import { AboutYou } from './pages/AboutYou';
import { Money } from './pages/Money';
import { Score } from './pages/Score';
import { Plan } from './pages/Plan';
import { hydrateStressEvents, type GpEvent } from './lib/stressEvents';
import {
  EMPTY_SESSION,
  NEED_TYPES,
  isNeedType,
  type ExtraNeed,
  type GpSession,
  type NeedRow,
  type NeedType,
  type Route,
} from './lib/types';
import { loadAuthSession } from './lib/auth';
import { postJson, sessionPayload, type PredictResponse, type ProjectResponse, type ScoreResponse } from './lib/api';
import { ASSUME_DEFAULTS, assumeChangedCount, investRetFromReturn } from './lib/assumptions';
import { clampAllWealthToCaps, productFlags } from './lib/planProducts';
import { buildExplainContext, type ExplainKind, type ExplainResponse } from './lib/explain';
import { applyMarkerMoveToSession, type ChartMarker } from './lib/chartMarkers';
import { applyDocs, seedProducts } from './lib/local';
import { isSvData, type ChartView, type SvData } from './lib/sv';
import { pauseSpeak, resumeSpeak, speak, stopSpeak } from './lib/speech';
import { capEnabledNeeds } from './lib/needEdit';
import { readGtTt, writeGtTt } from './lib/gtTt';

const PLU_UNAVAILABLE =
  '360-PeopleLikeU(r) is not available, so we cannot predict your financial future.';

function skeletonNeed(type: NeedType, prev?: NeedRow): NeedRow {
  return {
    type,
    enabled: prev?.enabled ?? (type === 'N_INC' || type === 'N_RET'),
    needAmount: 0,
    existing: 0,
    gap: 0,
    priority: 3,
  };
}

function applyPredict(s: GpSession, p: PredictResponse['session']): GpSession {
  const skip = s.moneyTouched;
  const incoming = Array.isArray(p.needs) ? p.needs.filter((n): n is NeedRow => isNeedType(n?.type)) : [];
  const mapped: NeedRow[] = incoming.map(n => {
    const prev = s.needs.find(x => x.type === n.type);
    const needAmount = n.needAmount || 0;
    const existing = n.existing || n.existingSumAssured || 0;
    return {
      ...n,
      needAmount,
      existing: existing || 0,
      gap: n.gap ?? Math.max(0, needAmount - existing),
      enabled: n.type === 'N_RET' ? true : prev ? prev.enabled : (n.enabled ?? false),
      retAge: n.retAge ?? prev?.retAge,
      targetYear: n.targetYear ?? prev?.targetYear,
    };
  });
  const seen = new Set(mapped.map(n => n.type));
  const needs = capEnabledNeeds(
    mapped.concat(NEED_TYPES.filter(t => !seen.has(t)).map(t => skeletonNeed(t, s.needs.find(n => n.type === t)))),
  );
  return {
    ...s,
    incomeMonthly: skip.income ? s.incomeMonthly : Number(p.incomeMonthly ?? s.incomeMonthly),
    expenseMonthly: skip.expense ? s.expenseMonthly : Number(p.expenseMonthly ?? s.expenseMonthly),
    cash: skip.cash || skip.savings ? s.cash : Number(p.cash ?? s.cash),
    investments: skip.investments || skip.savings ? s.investments : Number(p.investments ?? s.investments),
    property: skip.property ? s.property : Number(p.property ?? s.property),
    mortgage: skip.loans ? s.mortgage : Number(p.mortgage ?? s.mortgage),
    policies: skip.cover ? s.policies : ((p.policies as GpSession['policies']) ?? s.policies),
    needs,
    source: p.source ?? s.source,
    note: p.note ?? s.note,
  };
}

const MONEY_PROV = ['income', 'expense', 'savings', 'cash', 'investments', 'property', 'loans', 'cover'] as const;

function resetPredictedMoney(s: GpSession): GpSession {
  const provenance = { ...s.provenance };
  for (const k of MONEY_PROV) delete provenance[k];
  return {
    ...s,
    incomeMonthly: 0,
    expenseMonthly: 0,
    cash: 0,
    investments: 0,
    property: 0,
    mortgage: 0,
    policies: [],
    needs: [],
    moneyTouched: {},
    provenance,
    source: undefined,
    note: undefined,
    prodSeeded: false,
    plansOff: [],
    planMth: {},
    planLump: {},
    planSum: {},
    planPrem: {},
  };
}

export default function App() {
  const [route, setRoute] = useState<Route>('d2cIntro');
  const [session, setSession] = useState<GpSession>(EMPTY_SESSION);
  const [busy, setBusy] = useState(false);
  const [pre, setPre] = useState<number | null>(null);
  const [post, setPost] = useState<number | null>(null);
  const [svData, setSvData] = useState<SvData | null>(null);
  const [svPayload, setSvPayload] = useState<Record<string, unknown> | null>(null);
  const [scoreError, setScoreError] = useState<string | null>(null);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [predictError, setPredictError] = useState<string | null>(null);
  const [toast, setToast] = useState('');
  const [miraOn, setMiraOn] = useState(false);
  const [narrKind, setNarrKind] = useState<ExplainKind | null>(null);
  const [narrPaused, setNarrPaused] = useState(false);
  const [gtTtOn, setGtTtOn] = useState(readGtTt);
  const [tourSeen, setTourSeen] = useState<Partial<Record<'about' | 'money' | 'score' | 'plan', boolean>>>({});
  const [reportOpen, setReportOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const token = loadAuthSession()?.access_token ?? null;
  const projectTimer = useRef<number | null>(null);
  const scoreTimer = useRef<number | null>(null);
  const sessionRef = useRef(session);
  const toastTimer = useRef<number | null>(null);
  const narrAbort = useRef<AbortController | null>(null);
  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  const patch = (p: Partial<GpSession>) => {
    setSession(s => {
      const next = {
        ...s,
        ...p,
        ...(p.planPrem ? { planPrem: { ...s.planPrem, ...p.planPrem } } : {}),
        ...(p.planSum ? { planSum: { ...s.planSum, ...p.planSum } } : {}),
        ...(p.planMth ? { planMth: { ...s.planMth, ...p.planMth } } : {}),
        ...(p.planLump ? { planLump: { ...s.planLump, ...p.planLump } } : {}),
      };
      if (
        route === 'd2cPlan' &&
        [
          'planMth',
          'planLump',
          'planSum',
          'planPrem',
          'plansOff',
          'investMth',
          'investLump',
          'investRet',
          'lifeSum',
          'lifePrem',
          'lifeOn',
          'criOn',
          'tpdOn',
          'investOn',
          'investmentReturn',
        ].some(k => k in p)
      ) {
        scheduleProject(next);
      }
      return next;
    });
  };

  const scheduleScore = useCallback(
    (s: GpSession) => {
      if (scoreTimer.current) window.clearTimeout(scoreTimer.current);
      scoreTimer.current = window.setTimeout(() => {
        void (async () => {
          try {
            const res = await postJson<ScoreResponse>('/v1/score', sessionPayload(s), token);
            setPre(res.preHappiU);
            setPost(res.postHappiU);
            setScoreError(null);
          } catch {
            /* keep the last score on a quiet refresh */
          }
        })();
      }, 500);
    },
    [token],
  );

  const patchScore = (p: Partial<GpSession>) => {
    setSession(s => {
      const next = { ...s, ...p };
      if (p.needs) scheduleScore(next);
      return next;
    });
  };

  const showToast = (msg: string) => {
    setToast(msg);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(''), 2800);
  };

  const setGtTt = (on: boolean) => {
    writeGtTt(on);
    setGtTtOn(on);
  };

  const go = (r: Route) => {
    const idx = ['d2cIntro', 'd2cAbout', 'd2cMoney', 'd2cScore', 'd2cPlan'].indexOf(r);
    setSession(s => ({ ...s, maxStep: Math.max(s.maxStep, idx) }));
    setRoute(r);
    if (r !== 'd2cPlan') {
      setReportOpen(false);
      setShareOpen(false);
    }
  };

  const estimate = async () => {
    setBusy(true);
    setPredictError(null);
    const current = applyDocs(resetPredictedMoney(sessionRef.current));
    sessionRef.current = current;
    setSession(current);
    try {
      const res = await postJson<PredictResponse>('/v1/predict', sessionPayload(current), token);
      setSession(s => applyDocs(applyPredict(s, res.session)));
      go('d2cMoney');
    } catch (err) {
      setPredictError(err instanceof Error && err.message ? err.message : PLU_UNAVAILABLE);
    } finally {
      setBusy(false);
    }
  };

  const score = async () => {
    setBusy(true);
    setScoreError(null);
    go('d2cScore');
    try {
      const res = await postJson<ScoreResponse>('/v1/score', sessionPayload(sessionRef.current), token);
      setPre(res.preHappiU);
      setPost(res.postHappiU);
    } catch {
      setPre(null);
      setScoreError('HappiU could not return a score. Check that the HappiU service is up and try again.');
    } finally {
      setBusy(false);
    }
  };

  const runProject = useCallback(
    async (s: GpSession) => {
      setBusy(true);
      try {
        const res = await postJson<ProjectResponse>('/v1/project', sessionPayload(s), token);
        const data = isSvData(res.data) ? res.data : null;
        setSvData(data);
        setSvPayload(res.payload && typeof res.payload === 'object' ? res.payload : null);
        setProjectError(data ? null : 'The projection did not return a wealth path.');
        const scored = await postJson<ScoreResponse>('/v1/score', sessionPayload(s), token);
        setPre(scored.preHappiU);
        setPost(scored.postHappiU);
      } catch (err) {
        setProjectError(err instanceof Error ? err.message : 'The projection could not be run.');
      } finally {
        setBusy(false);
      }
    },
    [token],
  );

  const openPlan = async (need?: NeedType) => {
    const seeded = { ...sessionRef.current, ...seedProducts(sessionRef.current) };
    const next = need ? { ...seeded, tip: `panel-plans:${need}` } : seeded;
    setSession(next);
    go('d2cPlan');
    await runProject(next);
  };

  const toggleNeed = (t: NeedType) => {
    setSession(s => {
      const needs = capEnabledNeeds(s.needs.map(n => (n.type === t ? { ...n, enabled: !n.enabled } : n)));
      const next = { ...s, needs, ...productFlags({ ...s, needs }) };
      if (route === 'd2cPlan') scheduleProject(next);
      return next;
    });
  };

  const toggleExtra = (k: ExtraNeed) => {
    setSession(s => ({
      ...s,
      extraNeeds: s.extraNeeds.includes(k) ? s.extraNeeds.filter(x => x !== k) : [...s.extraNeeds, k],
    }));
  };

  const toggleEvent = (id: string) => {
    setSession(s => {
      const events = hydrateStressEvents(s.events).map(e => (e.id === id ? { ...e, on: !e.on } : e));
      const next = { ...s, events };
      scheduleProject(next);
      return next;
    });
  };

  const setEvents = (events: GpEvent[]) => {
    setSession(s => {
      const next = { ...s, events: hydrateStressEvents(events) };
      scheduleProject(next);
      return next;
    });
  };

  const setAssume = (p: Partial<GpSession>) => {
    setSession(s => {
      const synced =
        p.investmentReturn != null ? { ...p, investRet: investRetFromReturn(p.investmentReturn) } : p;
      const next = { ...s, ...synced };
      const caps = synced.investmentReturn != null ? clampAllWealthToCaps(next) : {};
      const out = { ...next, ...caps };
      if (route === 'd2cPlan') scheduleProject(out);
      return out;
    });
  };

  const resetAssume = () => setAssume({ ...ASSUME_DEFAULTS });

  const moveMarker = (marker: ChartMarker, newX: number) => {
    setSession(s => {
      const next = applyMarkerMoveToSession(s, marker, newX);
      scheduleProject(next);
      return next;
    });
  };

  const clickMarker = (marker: ChartMarker) => {
    const id = marker.id === 'retirement' ? 'N_RET' : marker.id;
    patch({ tip: marker.kind === 'event' ? `panel-events:${id}` : `panel-goals:${id}` });
  };

  function scheduleProject(s: GpSession) {
    if (projectTimer.current) window.clearTimeout(projectTimer.current);
    projectTimer.current = window.setTimeout(() => {
      void runProject(s);
    }, 500);
  }

  const stopVoice = () => {
    narrAbort.current?.abort();
    narrAbort.current = null;
    stopSpeak();
    setMiraOn(false);
    setNarrKind(null);
    setNarrPaused(false);
  };

  const narrate = (kind: ExplainKind, extras?: { chartView?: ChartView }) => {
    const same = narrKind === kind || (kind === 'mira' && miraOn);
    if (same) {
      if (narrPaused) {
        resumeSpeak();
        setNarrPaused(false);
        return;
      }
      if (pauseSpeak()) {
        setNarrPaused(true);
        return;
      }
      stopVoice();
      return;
    }
    stopSpeak();
    narrAbort.current?.abort();
    const ac = new AbortController();
    narrAbort.current = ac;
    setNarrPaused(false);
    if (kind === 'mira') {
      setMiraOn(true);
      setNarrKind(null);
    } else {
      setMiraOn(false);
      setNarrKind(kind);
    }
    if (kind === 'money') patch({ explain: true });
    const context = buildExplainContext({
      kind,
      route,
      session: sessionRef.current,
      pre,
      post,
      svData,
      chartView: extras?.chartView,
    });
    void postJson<ExplainResponse>('/v1/explain', { kind, route, context }, token, ac.signal)
      .then(res => {
        if (ac.signal.aborted) return;
        const ok = speak(res.text, () => {
          setMiraOn(false);
          setNarrKind(null);
          setNarrPaused(false);
        });
        if (!ok) {
          setMiraOn(false);
          setNarrKind(null);
          setNarrPaused(false);
          showToast('Voice playback is not available in this browser');
        }
      })
      .catch(err => {
        if (ac.signal.aborted || (err instanceof Error && err.name === 'AbortError')) return;
        setMiraOn(false);
        setNarrKind(null);
        setNarrPaused(false);
        showToast('Could not generate the explanation');
      });
  };

  useEffect(() => {
    return () => {
      if (projectTimer.current) window.clearTimeout(projectTimer.current);
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
      narrAbort.current?.abort();
      stopSpeak();
    };
  }, []);

  const nAssume = assumeChangedCount(session);
  const assumeOpen = session.tip?.startsWith('panel-assume') ?? false;

  return (
    <Shell
      route={route}
      maxStep={session.maxStep}
      onGo={go}
      toast={toast}
      miraOn={miraOn}
      miraPaused={narrPaused && miraOn}
      onMira={() => narrate('mira')}
      onToast={showToast}
      gtTtOn={gtTtOn}
      onGtTtToggle={() => {
        const next = !gtTtOn;
        setGtTt(next);
        if (next) setTourSeen({});
      }}
      onShare={undefined}
      nAssume={nAssume}
      assumeOn={assumeOpen}
      onAssume={() => patch({ tip: assumeOpen ? null : 'panel-assume' })}
      overlay={
        assumeOpen ? (
          <AssumeModal
            session={session}
            nAssume={nAssume}
            onClose={() => patch({ tip: null })}
            onAssume={setAssume}
            onAssumeReset={resetAssume}
          />
        ) : null
      }
    >
      {route === 'd2cIntro' && (
        <Intro
          narrOn={narrKind === 'intro'}
          narrPaused={narrPaused}
          onNarr={() => narrate('intro')}
          onStart={() => go('d2cAbout')}
        />
      )}
      {route === 'd2cAbout' && (
        <AboutYou
          session={session}
          onChange={patch}
          onBack={() => go('d2cIntro')}
          onEstimate={() => void estimate()}
          busy={busy}
          predictError={predictError}
          onToast={showToast}
          gtTtOn={gtTtOn && !tourSeen.about}
          onGtTtComplete={() => setTourSeen(s => ({ ...s, about: true }))}
        />
      )}
      {route === 'd2cMoney' && (
        <Money
          session={session}
          onChange={patch}
          onBack={() => go('d2cAbout')}
          onReestimate={() => void estimate()}
          onScore={() => void score()}
          busy={busy}
          predictError={predictError}
          narrOn={narrKind === 'money'}
          narrPaused={narrPaused}
          onNarr={() => narrate('money')}
          gtTtOn={gtTtOn && !tourSeen.money}
          onGtTtComplete={() => setTourSeen(s => ({ ...s, money: true }))}
        />
      )}
      {route === 'd2cScore' && (
        <Score
          session={session}
          pre={pre}
          scoreError={scoreError}
          onChange={patchScore}
          onBack={() => go('d2cMoney')}
          onPlan={need => void openPlan(need)}
          onToggleNeed={toggleNeed}
          onToggleExtra={toggleExtra}
          busy={busy}
          narrKind={narrKind}
          narrPaused={narrPaused}
          onNarr={kind => narrate(kind)}
          gtTtOn={gtTtOn && !tourSeen.score}
          onGtTtComplete={() => setTourSeen(s => ({ ...s, score: true }))}
        />
      )}
      {route === 'd2cPlan' && (
        <Plan
          session={session}
          pre={pre}
          post={post}
          svData={svData}
          svPayload={svPayload}
          projectError={projectError}
          onChange={patch}
          onBack={() => go('d2cScore')}
          onToggleNeed={toggleNeed}
          onToggleExtra={toggleExtra}
          onToggleEvent={toggleEvent}
          onEvents={setEvents}
          onMarkerMove={moveMarker}
          onMarkerClick={clickMarker}
          busy={busy}
          narrKind={narrKind}
          narrPaused={narrPaused}
          onNarr={(k, extras) => narrate(k, extras)}
          onToast={showToast}
          reportOpen={reportOpen}
          onReportOpenChange={setReportOpen}
          shareOpen={shareOpen}
          onShareOpenChange={setShareOpen}
          gtTtOn={gtTtOn && !tourSeen.plan}
          onGtTtComplete={() => {
            setTourSeen(s => ({ ...s, plan: true }));
            setGtTt(false);
          }}
        />
      )}
    </Shell>
  );
}
