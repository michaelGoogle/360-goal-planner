import { useEffect, useRef, useState, type ReactNode } from 'react';
import { HappiUGauge } from '../../components/HappiUGauge';
import { EqPie, GroupTag } from '../../components/ui';
import { Ico } from '../../lib/icons';
import { getJson } from '../../lib/api';
import {
  EXTRA_NEEDS,
  NEED_META,
  POLICY_COL,
  assets,
  availableBudget,
  chartMoneyOut,
  firstName,
  happiBand,
  happiCaption,
  HAPPI_COL,
  money,
  netWealth,
  sessionAge,
  type GpSession,
} from '../../lib/types';
import type { SvData } from '../../lib/sv';
import { ReportWalkthrough, ReportWalkthroughStill } from './ReportWalkthrough';
import {
  assumeLabel,
  changedAssumptions,
  goalRows,
  planLines,
  ratioSummary,
  reportPrintedOn,
  rnum,
} from './reportModel';
import { planAfford } from '../../lib/planProducts';

const REPORT_JUMP = [
  ['rpt-video', 'Video'],
  ['rpt-about', 'About you'],
  ['rpt-money', 'Your money'],
  ['rpt-goals', 'Your goals'],
  ['rpt-score', 'Your score'],
  ['rpt-plan', 'Your plan'],
] as const;

function ReportSec({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <details id={id} className="x-rpt-sec" open>
      <summary>{title}</summary>
      {children}
    </details>
  );
}

export function PlanReport({
  session,
  pre,
  post,
  onClose,
  onShare,
  onChange,
}: {
  session: GpSession;
  pre: number | null;
  post: number | null;
  svData: SvData | null;
  onClose: () => void;
  onShare: () => void;
  onChange: (p: Partial<GpSession>) => void;
}) {
  const who = firstName(session);
  const age = sessionAge(session);
  const today = reportPrintedOn();
  const score = post ?? pre ?? 0;
  const band = happiBand(score);
  const lift = pre != null && post != null ? Math.round(post) - Math.round(pre) : null;
  const liftCopy =
    lift != null && lift > 0
      ? band === 'GOOD'
        ? 'Through a smart selection of these plans you are much better off and in good shape.'
        : band === 'FAIR'
          ? 'Through a smart selection of these plans you are better off — a solid start. Close the largest gaps to lift this further.'
          : 'These plans lift your HappiU. Start with the biggest shortfall to get on firmer ground.'
      : happiCaption(score);
  const goals = goalRows(session);
  const ratios = ratioSummary(session);
  const afford = planAfford(session);
  const plans = planLines(session);
  const assume = changedAssumptions(session);
  const eventsOn = session.events.filter(e => e.on);
  const extras = EXTRA_NEEDS.filter(x => session.extraNeeds.includes(x.k));
  const moneyKeys = ['income', 'expense', 'cash', 'investments', 'property', 'loans', 'cover'] as const;
  const mInc = session.incomeMonthly;
  const surplus = availableBudget(session);
  const net = netWealth(session);

  useEffect(() => {
    const html = document.documentElement;
    html.classList.add('x-report-open');
    document.body.classList.add('x-report-open');
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      html.classList.remove('x-report-open');
      document.body.classList.remove('x-report-open');
      window.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  const hasContact = Boolean(session.reportMobile);
  const jobId = session.reportJobId || '';
  const videoStatus =
    session.reportVideoStatus === 'completed' ||
    session.reportVideoStatus === 'failed' ||
    session.reportVideoStatus === 'pending'
      ? session.reportVideoStatus
      : 'idle';
  const [dummyUrl, setDummyUrl] = useState('');

  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    const ac = new AbortController();
    const fallback = 'https://mgzh11.synology.me:8442/videos/gp/generic-walkthrough.mp4';
    let gone = false;
    void getJson<{ dummyUrl?: string }>('/v1/report-walkthrough', ac.signal)
      .then(data => {
        if (!gone) setDummyUrl(data.dummyUrl || fallback);
      })
      .catch(err => {
        if (gone || (err instanceof Error && err.name === 'AbortError')) return;
        setDummyUrl(fallback);
      });
    return () => {
      gone = true;
      ac.abort();
    };
  }, []);

  useEffect(() => {
    if (!hasContact || !jobId) return;
    if (videoStatus === 'completed' && session.reportMediaUrl) return;
    if (videoStatus === 'failed') return;
    let gone = false;
    const tick = () => {
      void getJson<{ status: string; mediaUrl?: string; error?: string }>(`/v1/video-notify/${jobId}`)
        .then(data => {
          if (gone) return;
          if (data.status === 'completed') {
            onChangeRef.current({
              reportVideoStatus: 'completed',
              reportMediaUrl: data.mediaUrl || '',
            });
            return;
          }
          if (data.status === 'failed') {
            onChangeRef.current({ reportVideoStatus: 'failed' });
          }
        })
        .catch(() => undefined);
    };
    tick();
    const id = window.setInterval(tick, 4000);
    return () => {
      gone = true;
      window.clearInterval(id);
    };
  }, [hasContact, jobId, videoStatus, session.reportMediaUrl]);

  return (
    <div className="x-report-ov" role="dialog" aria-modal="true" aria-labelledby="x-rpt-title">
      <div className="x-report-bar">
        <span className="sp" />
        <button className="x-assumb" type="button" onClick={onShare}>
          {Ico.share}Share report
        </button>
        <button className="x-btn g" type="button" onClick={onClose}>
          {Ico.close} Close
        </button>
      </div>

      <article className="x-report">
        <header className="x-rpt-hero">
          <p className="x-eyebrow">FinPlan360 · Powered by 360F</p>
          <h1 id="x-rpt-title">{who === 'you' ? 'Your plan report' : `${who}’s plan report`}</h1>
          <p className="x-lead">
            Snapshot of this session on {today}
            {age ? ` · age ${age}` : ''}. Figures match Your plan. Not a quote, and not advice to buy.
          </p>
          <div className="x-rpt-scores">
            <div className="x-rpt-gauge">
              <span>Your new HappiU Score</span>
              <HappiUGauge value={score} size={200} showBand={false} />
            </div>
            <div className="x-rpt-score-side">
              {lift != null && lift !== 0 ? (
                <b className="x-rpt-lift" style={{ color: lift > 0 ? HAPPI_COL.GOOD : HAPPI_COL.POOR }}>
                  {lift > 0 ? `+${lift}` : lift}
                </b>
              ) : null}
              <p className="x-scorecap" style={{ color: HAPPI_COL[band], textAlign: 'left' }}>
                {lift != null && lift !== 0 ? `uplift. ${liftCopy}` : liftCopy}
              </p>
            </div>
          </div>
        </header>

        <nav className="x-rpt-jump" aria-label="Jump to report section">
          {REPORT_JUMP.map(([id, label]) => (
            <a key={id} href={`#${id}`}>
              {label}
            </a>
          ))}
        </nav>

        <div id="rpt-video">
          <ReportWalkthrough
            who={who}
            dummyUrl={dummyUrl}
            mediaUrl={session.reportMediaUrl || ''}
            status={videoStatus}
          />
          <ReportWalkthroughStill who={who} />
        </div>

        <ReportSec id="rpt-about" title="About you">
          <dl className="x-rpt-dl">
            <div><dt>Name</dt><dd>{session.name.trim() || '—'}</dd></div>
            <div><dt>Age</dt><dd>{age ?? '—'}</dd></div>
            <div><dt>Occupation</dt><dd>{session.occupation || '—'}</dd></div>
            <div><dt>Residency</dt><dd>{session.residency || '—'}</dd></div>
            <div><dt>Dependants</dt><dd>{session.dependents}</dd></div>
            <div><dt>Retire at</dt><dd>{session.ageOfRetirement}</dd></div>
          </dl>
        </ReportSec>

        <ReportSec id="rpt-money" title="Your money">
          <p className="x-rpt-note">
            <GroupTag session={session} keys={[...moneyKeys]} verb="usually look like this" />
          </p>

          <h3>What comes in and goes out</h3>
          <div className="x-rpt-chart">
            <EqPie
              rows={[
                { l: 'Money coming in', v: mInc, c: 'pos' },
                { l: 'Money going out', v: chartMoneyOut(session), c: 'neg' },
                { l: surplus < 0 ? 'Short each month' : 'Available budget', v: surplus, c: surplus < 0 ? 'neg' : 'tot' },
              ]}
            />
          </div>

          <h3>What you own and owe</h3>
          <div className="x-rpt-chart">
            <EqPie
              rows={[
                { l: 'Assets', v: assets(session), c: 'pos' },
                { l: 'Loans outstanding', v: session.mortgage, c: 'neg' },
                { l: net < 0 ? 'Negative net wealth' : 'Net wealth', v: net, c: net < 0 ? 'neg' : 'tot' },
              ]}
            />
          </div>

          <dl className="x-rpt-dl">
            <div><dt>Cash &amp; Savings</dt><dd>{money(session.cash)}</dd></div>
            <div><dt>Investments</dt><dd>{money(session.investments)}</dd></div>
            <div><dt>Property</dt><dd>{money(session.property)}</dd></div>
          </dl>

          <h3>What cover you have</h3>
          {session.policies.length ? (
            <>
              <div className="x-rpt-chart">
                <EqPie
                  rows={session.policies.map(p => ({
                    l: p.type,
                    v: p.sum,
                    fill: POLICY_COL[p.type] || '#7086FD',
                  }))}
                />
              </div>
              <table className="x-rpt-table">
                <caption>Existing cover</caption>
                <thead>
                  <tr><th>Type</th><th>Insurer</th><th>Sum</th><th>Premium / yr</th></tr>
                </thead>
                <tbody>
                  {session.policies.map(p => (
                    <tr key={`${p.type}-${p.insurer}-${p.sum}`}>
                      <td>{p.type}</td>
                      <td>{p.insurer || '—'}</td>
                      <td>{money(p.sum)}</td>
                      <td>{money(p.premium)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p className="x-sm">No existing policies on this session.</p>
          )}
        </ReportSec>

        <ReportSec id="rpt-goals" title="Your goals">
          <table className="x-rpt-table">
            <thead>
              <tr><th>Goal</th><th>On</th><th>Need</th><th>Have</th><th>Gap</th></tr>
            </thead>
            <tbody>
              {goals.map(n => (
                <tr key={n.type} className={n.enabled ? '' : 'off'}>
                  <td>{NEED_META[n.type].label}</td>
                  <td>{n.enabled ? 'Yes' : 'Off'}</td>
                  <td>{money(n.needAmount || 0)}</td>
                  <td>{money(n.have)}</td>
                  <td>{n.enabled ? money(n.gap) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {extras.length ? (
            <p className="x-sm">Also on: {extras.map(x => x.label).join(', ')}.</p>
          ) : null}
        </ReportSec>

        <ReportSec id="rpt-score" title="Your score">
          <p className="x-sm">{ratios.ok} of {ratios.rows.length} money-health ratios are in good shape.</p>
          <table className="x-rpt-table">
            <thead>
              <tr><th>Ratio</th><th>You</th><th>Recommended</th><th></th></tr>
            </thead>
            <tbody>
              {ratios.rows.map(r => (
                <tr key={r.k}>
                  <td>{r.n}</td>
                  <td>{rnum(r.v)}{r.unit === '%' ? '%' : ` ${r.unit}`}</td>
                  <td>{r.rec}</td>
                  <td className={r.ok ? 'ok' : 'no'}>{r.ok ? 'In range' : 'Outside'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReportSec>

        <ReportSec id="rpt-plan" title="Your plan">
          <dl className="x-rpt-dl">
            <div><dt>Monthly surplus</dt><dd>{money(afford.available)}</dd></div>
            <div><dt>Recommended free budget ({afford.freePct}%)</dt><dd>{money(afford.free)}</dd></div>
            <div><dt>Premiums &amp; contributions</dt><dd>{money(afford.monthly)} / mo</dd></div>
            <div>
              <dt>Budget fit</dt>
              <dd className={afford.monthlyOver > 0 ? 'no' : 'ok'}>
                {afford.monthlyOver > 0 ? `${money(afford.monthlyOver)} over` : 'Fits'}
              </dd>
            </div>
          </dl>
          {plans.length ? (
            <table className="x-rpt-table">
              <thead>
                <tr><th>Suggested product</th><th>In plan</th><th>Sizing</th><th>Remaining gap</th></tr>
              </thead>
              <tbody>
                {plans.map(p => (
                  <tr key={p.type}>
                    <td>{p.title}</td>
                    <td>{p.on ? 'Yes' : 'Off'}</td>
                    <td>{p.detail}</td>
                    <td>{p.remain > 0 ? money(p.remain) : 'Closed'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="x-sm">Every activated goal is already funded.</p>
          )}
          {eventsOn.length ? (
            <p className="x-sm">Stress tests on: {eventsOn.map(e => e.label).join(', ')}.</p>
          ) : (
            <p className="x-sm">No stress tests are on.</p>
          )}
          {assume.length ? (
            <p className="x-sm">
              Assumptions changed from default:{' '}
              {assume.map(a => `${assumeLabel(a.key)} ${a.value} (was ${a.base})`).join('; ')}.
            </p>
          ) : (
            <p className="x-sm">Projection uses the default Singapore assumption set.</p>
          )}
        </ReportSec>

        <footer className="x-rpt-foot">
          People Like You figures are estimates until you edit them or add a statement. This report is not a product
          quote, application, or purchase, and it is not advice to buy, switch, or cancel cover.
        </footer>
      </article>
    </div>
  );
}
