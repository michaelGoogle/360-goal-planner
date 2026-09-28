import { useCallback, useEffect, useRef, useState } from 'react';
import { Shell } from './components/Shell';
import { AssumeModal } from './components/AssumeModal';
import { Intro } from './pages/Intro';
import { AboutYou } from './pages/AboutYou';
import { Money } from './pages/Money';
import { Score } from './pages/Score';
import { Plan } from './pages/Plan';
import { defaultStressEvents, hydrateStressEvents, stressEventsFromParameters, type GpEvent } from './lib/stressEvents';
import {
  EMPTY_SESSION,
  NEED_TYPES,
  isNeedType,
  type GpSession,
  type NeedRow,
  type NeedType,
  type Route,
} from './lib/types';
import { loadAuthSession } from './lib/auth';
import { postJson, sessionPayload, type NeedsResponse, type PredictResponse, type ProjectResponse, type ScoreResponse } from './lib/api';
import { sessionCountry } from './lib/currency';
import { assumeChangedCount, investRetFromReturn } from './lib/assumptions';
import {
  ASSUME_CONFIG_FALLBACK,
  ASSUME_FALLBACK as ASSUME_DEFAULTS,
  ASSUME_KEYS,
  assumeConfigFrom,
  assumeDefaults,
  fetchAssumptionSchema,
  fetchParameters,
  fetchSessionDefaults,
  type AssumeConfig,
} from './lib/config';
import { clampAllWealthToCaps, productFlags, refreshUntouchedCover } from './lib/planProducts';
import { buildExplainContext, type ExplainKind, type ExplainResponse } from './lib/explain';
import { applyMarkerMoveToSession, type ChartMarker } from './lib/chartMarkers';
import { applyDocs, seedProductsFromApi } from './lib/local';
import { riskSessionPatch } from './lib/riskCapacity';
import { isSvData, type ChartView, type SvData } from './lib/sv';
import { pauseSpeak, resumeSpeak, speak, stopSpeak } from './lib/speech';
import { capEnabledNeeds, minExpenseMonthly, needsProvenanceYou, toggleNeedEnabled } from './lib/needEdit';
import { readGtTt, writeGtTt } from './lib/gtTt';
import { useIsMobile } from './hooks/useIsMobile';

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
      have: n.have ?? prev?.have ?? 0,
      gap: n.gap ?? Math.max(0, needAmount - (n.have ?? (existing || 0))),
      enabled: n.type === 'N_RET' ? true : prev ? prev.enabled : (n.enabled ?? false),
      retAge: n.retAge ?? prev?.retAge,
      targetYear: n.targetYear ?? prev?.targetYear,
      ltcStartAge: n.ltcStartAge ?? prev?.ltcStartAge,
    };
  });
  const seen = new Set(mapped.map(n => n.type));
  const property = skip.property ? s.property : Number(p.property ?? s.property);
  const needs = capEnabledNeeds(
    mapped.concat(NEED_TYPES.filter(t => !seen.has(t)).map(t => skeletonNeed(t, s.needs.find(n => n.type === t)))),
  );
  const next: GpSession = {
    ...s,
    incomeMonthly: skip.income ? s.incomeMonthly : Number(p.incomeMonthly ?? s.incomeMonthly),
    expenseMonthly: skip.expense ? s.expenseMonthly : Number(p.expenseMonthly ?? s.expenseMonthly),
    cash: skip.cash || skip.savings ? s.cash : Number(p.cash ?? s.cash),
    investments: skip.investments || skip.savings ? s.investments : Number(p.investments ?? s.investments),
    property,
    mortgage: skip.loans ? s.mortgage : Number(p.mortgage ?? s.mortgage),
    policies: skip.cover ? s.policies : ((p.policies as GpSession['policies']) ?? s.policies),
    needs,
    ageOfRetirement: Number(p.ageOfRetirement ?? s.ageOfRetirement),
    source: p.source ?? s.source,
    note: p.note ?? s.note,
    parkedNeeds: Array.isArray(p.parkedNeeds) ? p.parkedNeeds : s.parkedNeeds,
    fx: p.fx ?? s.fx,
    country: p.country ?? s.country,
    currency: p.currency ?? s.currency,
    ltcStartAge: p.ltcStartAge ?? s.ltcStartAge,
  };
  const le = Number(p.lifeExpectancy);
  if (Number.isFinite(le) && le >= 70 && le <= 120) {
    next.lifeExpectancy = le;
    next.endAge = le;
  }
  return next;
}

function mergePartial(s: GpSession, p: Partial<GpSession>): GpSession {
  return {
    ...s,
    ...p,
    ...(p.planPrem ? { planPrem: { ...s.planPrem, ...p.planPrem } } : {}),
    ...(p.planSum ? { planSum: { ...s.planSum, ...p.planSum } } : {}),
    ...(p.planMth ? { planMth: { ...s.planMth, ...p.planMth } } : {}),
    ...(p.planLump ? { planLump: { ...s.planLump, ...p.planLump } } : {}),
    ...(p.planSumTouched ? { planSumTouched: { ...s.planSumTouched, ...p.planSumTouched } } : {}),
    ...(p.planPremTouched ? { planPremTouched: { ...s.planPremTouched, ...p.planPremTouched } } : {}),
    ...(p.planMthTouched ? { planMthTouched: { ...s.planMthTouched, ...p.planMthTouched } } : {}),
    ...(p.planLumpTouched ? { planLumpTouched: { ...s.planLumpTouched, ...p.planLumpTouched } } : {}),
  };
}

function withRisk(s: GpSession, p: Partial<GpSession> = {}): GpSession {
  const merged = mergePartial(s, p);
  const risk = riskSessionPatch(merged);
  let out = { ...merged, ...risk };
  if (risk.investmentReturn != null && out.prodSeeded) {
    out = { ...out, ...clampAllWealthToCaps(out) };
  }
  return out;
}

const MONEY_PROV = ['income', 'expense', 'savings', 'cash', 'investments', 'property', 'loans', 'cover'] as const;

const NEED_INPUT_KEYS: (keyof GpSession)[] = [
  'needs',
  'incomeMonthly',
  'expenseMonthly',
  'cash',
  'investments',
  'policies',
  'mortgage',
  'dependents',
  'inflationRate',
  'investmentReturn',
  'ageOfRetirement',
  'age',
];

function needsInputChanged(p: Partial<GpSession>): boolean {
  return NEED_INPUT_KEYS.some(k => k in p);
}

const SCORE_REFRESH_KEYS: (keyof GpSession)[] = [
  'interestRate',
  'loanRate',
  'assetReturn',
  'incomeGrowthRate',
  'cash',
  'investments',
  'property',
];

function scoreInputChanged(p: Partial<GpSession>): boolean {
  return SCORE_REFRESH_KEYS.some(k => k in p);
}

function mergeNeedsFromApi(s: GpSession, incoming: NeedRow[], ageOfRetirement?: number): GpSession {
  const byType = new Map(incoming.filter(n => isNeedType(n.type)).map(n => [n.type, n]));
  const needs = s.needs.map(local => {
    const n = byType.get(local.type);
    if (!n) return local;
    return { ...local, ...n, enabled: local.enabled };
  });
  const seen = new Set(needs.map(n => n.type));
  for (const n of incoming) {
    if (!isNeedType(n.type) || seen.has(n.type)) continue;
    needs.push(n);
  }
  return {
    ...s,
    needs,
    ageOfRetirement: ageOfRetirement ?? s.ageOfRetirement,
  };
}

function resetPredictedMoney(s: GpSession): GpSession {
  const provenance = { ...s.provenance };
  for (const k of MONEY_PROV) delete provenance[k];
  delete provenance.needs;
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
    planSumTouched: {},
    planPremTouched: {},
    investmentReturnTouched: false,
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
  const [assumeConfig, setAssumeConfig] = useState<AssumeConfig>(ASSUME_CONFIG_FALLBACK);
  const token = loadAuthSession()?.access_token ?? null;
  const projectTimer = useRef<number | null>(null);
  const scoreTimer = useRef<number | null>(null);
  const needsTimer = useRef<number | null>(null);
  const needsAbort = useRef<AbortController | null>(null);
  const sessionRef = useRef(session);
  const toastTimer = useRef<number | null>(null);
  const narrAbort = useRef<AbortController | null>(null);
  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  const stopVoice = () => {
    narrAbort.current?.abort();
    narrAbort.current = null;
    stopSpeak();
    setMiraOn(false);
    setNarrKind(null);
    setNarrPaused(false);
  };

  const patch = (p: Partial<GpSession>) => {
    if (p.explain === false) stopVoice();
    setSession(s => {
      const next = withRisk(s, p);
      if (needsInputChanged(p)) scheduleNeeds(next);
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
          'riskTolerance',
        ].some(k => k in p)
      ) {
        scheduleProject(next);
      }
      return next;
    });
  };

  const applyNeedsResponse = useCallback(
    (s: GpSession, res: NeedsResponse): GpSession => {
      const merged = mergeNeedsFromApi(s, res.session.needs || [], res.session.ageOfRetirement);
      const cover = refreshUntouchedCover(merged);
      const next = { ...merged, ...cover };
      setSession(next);
      sessionRef.current = next;
      return next;
    },
    [],
  );

  const scheduleNeeds = useCallback(
    (s: GpSession) => {
      if (!s.needs.length) return;
      if (needsTimer.current) window.clearTimeout(needsTimer.current);
      needsTimer.current = window.setTimeout(() => {
        const latest = sessionRef.current;
        needsAbort.current?.abort();
        const ac = new AbortController();
        needsAbort.current = ac;
        void (async () => {
          try {
            const res = await postJson<NeedsResponse>('/v1/needs', sessionPayload(latest), token, ac.signal);
            if (ac.signal.aborted) return;
            const merged = applyNeedsResponse(sessionRef.current, res);
            if (route === 'd2cScore') scheduleScore(merged);
            if (route === 'd2cPlan') scheduleProject(merged);
          } catch (err) {
            if (ac.signal.aborted || (err instanceof Error && err.name === 'AbortError')) return;
          }
        })();
      }, 200);
    },
    [applyNeedsResponse, route, token],
  );

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
      const next = withRisk(s, p);
      if (needsInputChanged(p)) scheduleNeeds(next);
      else if (next.riskProfile !== s.riskProfile || scoreInputChanged(p)) scheduleScore(next);
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
    stopVoice();
    const idx = ['d2cIntro', 'd2cAbout', 'd2cMoney', 'd2cScore', 'd2cPlan'].indexOf(r);
    setSession(s => ({ ...s, maxStep: Math.max(s.maxStep, idx) }));
    setRoute(r);
    if (r !== 'd2cPlan') {
      setReportOpen(false);
      setShareOpen(false);
    }
    const main = document.getElementById('main');
    if (main) main.scrollTop = 0;
    window.scrollTo(0, 0);
  };

  const estimate = async () => {
    setBusy(true);
    setPredictError(null);
    const current = applyDocs(resetPredictedMoney(sessionRef.current));
    sessionRef.current = current;
    setSession(current);
    try {
      const res = await postJson<PredictResponse>('/v1/predict', sessionPayload(current), token);
      let next = withRisk(applyDocs(applyPredict(current, res.session)));
      try {
        const params = await fetchParameters(next.parametersVersion);
        const values = Object.fromEntries(
          Object.entries(params.parameters).map(([k, p]) => [k, Number(p.value)]),
        );
        if (next.fx && !next.events.some(e => e.on)) {
          const age = typeof next.age === 'number' ? next.age : 40;
          next = {
            ...next,
            events: defaultStressEvents(stressEventsFromParameters(values, next.fx.usdPerLocal, age)),
          };
        }
      } catch {
        /* catalog defaults stay */
      }
      setSession(next);
      sessionRef.current = next;
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
    let current = withRisk(sessionRef.current);
    try {
      const spendFloor = minExpenseMonthly(current);
      if ((current.expenseMonthly || 0) < spendFloor) {
        current = { ...current, expenseMonthly: spendFloor };
      }
      if (current.needs.length) {
        const needsRes = await postJson<NeedsResponse>('/v1/needs', sessionPayload(current), token);
        current = mergeNeedsFromApi(current, needsRes.session.needs || [], needsRes.session.ageOfRetirement);
      }
      sessionRef.current = current;
      setSession(current);
      go('d2cScore');
      const res = await postJson<ScoreResponse>('/v1/score', sessionPayload(current), token);
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
        const msg = err instanceof Error ? err.message : 'The projection could not be run.';
        const friendly =
          /retirement|retAge|ret.?age/i.test(msg) && /70|max|above|invalid/i.test(msg)
            ? 'Retirement age cannot be above 70.'
            : /^\s*[{\[]/.test(msg)
              ? 'The projection could not be run.'
              : msg;
        setProjectError(friendly);
      } finally {
        setBusy(false);
      }
    },
    [token],
  );

  const openPlan = async (need?: NeedType) => {
    let synced = withRisk(sessionRef.current);
    try {
      if (synced.needs.length) {
        const needsRes = await postJson<NeedsResponse>('/v1/needs', sessionPayload(synced), token);
        synced = mergeNeedsFromApi(synced, needsRes.session.needs || [], needsRes.session.ageOfRetirement);
      }
    } catch {
      /* keep last need amounts */
    }
    const seeded = { ...synced, ...(await seedProductsFromApi(synced, token)) };
    const next = need ? { ...seeded, tip: `panel-plans:${need}` } : seeded;
    setSession(next);
    sessionRef.current = next;
    go('d2cPlan');
    await runProject(next);
  };

  const toggleNeed = (t: NeedType) => {
    setSession(s => {
      const needs = toggleNeedEnabled(s.needs, t);
      const changed = needs.some((n, i) => n.enabled !== s.needs[i]?.enabled);
      const next = {
        ...s,
        needs,
        ...productFlags({ ...s, needs }),
        ...(changed ? { provenance: needsProvenanceYou(s) } : {}),
      };
      if (route === 'd2cPlan') scheduleProject(next);
      return next;
    });
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
      const marked =
        p.investmentReturn != null
          ? { ...p, investRet: investRetFromReturn(p.investmentReturn), investmentReturnTouched: true }
          : p;
      const next = withRisk(s, marked);
      const caps = marked.investmentReturn != null ? clampAllWealthToCaps(next) : {};
      const out = { ...next, ...caps };
      if (needsInputChanged(marked)) scheduleNeeds(out);
      else if (scoreInputChanged(marked) && route === 'd2cScore') scheduleScore(out);
      if (route === 'd2cPlan') scheduleProject(out);
      return out;
    });
  };

  const resetAssume = () => setAssume(assumeDefaults(assumeConfig));

  const moveMarker = (marker: ChartMarker, newX: number) => {
    setSession(s => {
      const next = applyMarkerMoveToSession(s, marker, newX);
      if (
        (marker.id === 'N_RET' || marker.id === 'retirement') &&
        Math.round(newX) > (next.ageOfRetirement || 0) &&
        next.ageOfRetirement === 70
      ) {
        showToast('Retirement age is capped at 70.');
      }
      if (marker.kind === 'need') scheduleNeeds(next);
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

  // The published rates and their bounds. Until this lands the modal shows the
  // built-in fallback, which is the same set the V0-24 workbook was calibrated on.
  // Any rate still sitting at that fallback adopts the published value, so an admin
  // who publishes a new version changes the session without the customer doing
  // anything; a rate the customer has already moved is left alone.
  useEffect(() => {
    let live = true;
    fetchAssumptionSchema()
      .then(schema => {
        if (!live) return;
        const config = assumeConfigFrom(schema);
        setAssumeConfig(config);
        const published = assumeDefaults(config);
        setSession(s => {
          const next: Partial<GpSession> = { parametersVersion: schema.version };
          for (const k of ASSUME_KEYS) {
            if (s[k] === ASSUME_DEFAULTS[k] && s[k] !== published[k]) next[k] = published[k];
          }
          return { ...s, ...next };
        });
        const age = typeof sessionRef.current.age === 'number' ? sessionRef.current.age : 40;
        return fetchSessionDefaults(age, sessionCountry(sessionRef.current)).then(defaults => {
          if (!live) return;
          setSession(s => ({
            ...s,
            ltcStartAge: s.ltcStartAge ?? defaults.ltcStartAge,
            goalTargetYears: s.goalTargetYears ?? defaults.targetYear,
            ageOfRetirement: s.ageOfRetirement === 65 ? defaults.ageOfRetirement : s.ageOfRetirement,
          }));
        });
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (projectTimer.current) window.clearTimeout(projectTimer.current);
      if (scoreTimer.current) window.clearTimeout(scoreTimer.current);
      if (needsTimer.current) window.clearTimeout(needsTimer.current);
      needsAbort.current?.abort();
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
      narrAbort.current?.abort();
      stopSpeak();
    };
  }, []);

  const isMobile = useIsMobile();
  const nAssume = assumeChangedCount(session, assumeConfig);
  const assumeOpen = !isMobile && (session.tip?.startsWith('panel-assume') ?? false);

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
      nAssume={isMobile ? undefined : nAssume}
      assumeOn={assumeOpen}
      onAssume={isMobile ? undefined : () => patch({ tip: assumeOpen ? null : 'panel-assume' })}
      session={session}
      pre={pre}
      post={post}
      onContactSaved={p =>
        setSession(s => ({
          ...s,
          reportEmail: p.email,
          reportMobile: p.mobile,
          insapiContactId: p.contactId || s.insapiContactId,
          insapiPlanId: p.planId || s.insapiPlanId,
        }))
      }
      overlay={
        assumeOpen ? (
          <AssumeModal
            session={session}
            nAssume={nAssume}
            assumeConfig={assumeConfig}
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
