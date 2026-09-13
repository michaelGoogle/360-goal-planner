import { useState, type ReactNode } from 'react';
import type { GpSession, Route } from '../lib/types';
import { ROUTES, ROUTE_LABEL } from '../lib/types';
import { suitePortalUrl } from '../lib/auth';
import { postJson, sessionPayload, type CrmSyncResponse } from '../lib/api';
import { Ico } from '../lib/icons';

export function Shell({
  route,
  maxStep,
  onGo,
  children,
  toast,
  miraOn,
  miraPaused,
  onMira,
  onToast,
  gtTtOn,
  onGtTtToggle,
  onShare: _onShare,
  nAssume,
  assumeOn,
  onAssume,
  overlay,
  session,
  pre,
  post,
  onContactSaved,
}: {
  route: Route;
  maxStep: number;
  onGo: (r: Route) => void;
  children: ReactNode;
  toast?: string;
  miraOn?: boolean;
  miraPaused?: boolean;
  onMira?: () => void;
  onToast?: (msg: string) => void;
  gtTtOn: boolean;
  onGtTtToggle: () => void;
  onShare?: () => void;
  nAssume?: number;
  assumeOn?: boolean;
  onAssume?: () => void;
  overlay?: ReactNode;
  session?: GpSession;
  pre?: number | null;
  post?: number | null;
  onContactSaved?: (p: {
    email: string;
    mobile: string;
    contactId?: string;
    planId?: string;
  }) => void;
}) {
  const cur = ROUTES.indexOf(route);
  const pct = Math.round((cur / (ROUTES.length - 1)) * 100);
  const [adv, setAdv] = useState(false);
  const [advSent, setAdvSent] = useState(false);
  const [advEmail, setAdvEmail] = useState('');
  const [advPhone, setAdvPhone] = useState('');
  const [advVia, setAdvVia] = useState('');
  const [advBusy, setAdvBusy] = useState(false);
  const [advErr, setAdvErr] = useState('');

  const sendAdv = () => {
    const em = advEmail.trim();
    const ph = advPhone.trim();
    if (!em || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) {
      setAdvErr('Enter an email address');
      return;
    }
    if (ph.replace(/\D/g, '').length < 8) {
      setAdvErr('Enter a mobile number');
      return;
    }
    setAdvErr('');
    setAdvBusy(true);
    const sess = session || ({} as GpSession);
    void postJson<CrmSyncResponse>('/v1/crm-sync', {
      email: em,
      mobile: ph,
      pre: pre ?? null,
      post: post ?? null,
      session: session ? sessionPayload(sess) : { name: '' },
    })
      .then(data => {
        setAdvVia(em);
        setAdvSent(true);
        setAdv(false);
        setAdvBusy(false);
        onContactSaved?.({
          email: em,
          mobile: ph,
          contactId: data.contactId,
          planId: data.planId,
        });
        onToast?.('An adviser will be in touch');
      })
      .catch(e => {
        setAdvBusy(false);
        setAdvErr(e instanceof Error && e.message ? e.message : 'Could not reach the adviser CRM');
      });
  };

  return (
    <div className="x">
      <header className="x-top">
        <a href={suitePortalUrl()} className="x-logo" style={{ textDecoration: 'none', color: 'inherit' }}>
          <i>F</i>
          <div>
            <b>FinPlan360</b>
            <span>Powered by 360F</span>
          </div>
        </a>
        <nav className="x-nav" aria-label="Progress">
          {ROUTES.map((r, i) => (
            <button
              key={r}
              type="button"
              className={`${i === cur ? 'on' : ''} ${i < cur ? 'done' : ''}`}
              disabled={i > maxStep}
              aria-current={i === cur ? 'step' : undefined}
              title={ROUTE_LABEL[r]}
              onClick={() => onGo(r)}
            >
              <i>{i < cur ? '✓' : i + 1}</i>
              <span>{ROUTE_LABEL[r]}</span>
            </button>
          ))}
        </nav>
        <div className="x-top-end">
          {onAssume ? (
            <button
              className={`x-top-assume ${assumeOn ? 'on' : ''}`}
              type="button"
              aria-pressed={!!assumeOn}
              aria-label="Assumptions"
              title="Assumptions"
              onClick={onAssume}
            >
              {Ico.sliders}
              <span>Assumptions</span>
              {nAssume ? <em className="x-assn">{nAssume}</em> : null}
            </button>
          ) : null}
          <button
            className={`x-gttt ${gtTtOn ? 'on' : ''}`}
            type="button"
            role="switch"
            aria-checked={gtTtOn}
            aria-label="Tool tips"
            title={gtTtOn ? 'Tool tips on' : 'Tool tips off'}
            onClick={onGtTtToggle}
          >
            <span className="x-gttt-l">Tool tips</span>
            <span className="x-togs">
              <i className="x-togk" />
            </span>
          </button>
        </div>
        <span className="x-bar" style={{ width: `${pct}%` }} />
      </header>
      <main className="canvas x-scroll" id="main" tabIndex={-1}>
        <div className="x-wrap">{children}</div>
      </main>
      {overlay}
      {adv ? (
        <div className="x-advp" role="dialog" aria-label="Talk to an adviser">
          <button className="cl" type="button" onClick={() => setAdv(false)} aria-label="Close">
            {Ico.close}
          </button>
          <b>Want a person to walk you through this?</b>
          <p>
            An adviser can go through your gaps with you, bring in products this tool does not price, and check the
            assumptions against your real position.
          </p>
          <div className="x-f">
            <label htmlFor="adv-email">Email</label>
            <input
              id="adv-email"
              className="x-in"
              value={advEmail}
              type="email"
              placeholder="you@example.com"
              autoComplete="email"
              disabled={advBusy}
              onChange={e => setAdvEmail(e.target.value)}
            />
          </div>
          <div className="x-f">
            <label htmlFor="adv-phone">Mobile</label>
            <input
              id="adv-phone"
              className="x-in"
              value={advPhone}
              type="tel"
              placeholder="+65 8123 4567"
              autoComplete="tel"
              disabled={advBusy}
              onChange={e => setAdvPhone(e.target.value)}
            />
          </div>
          {advErr ? <p className="x-ferr">{advErr}</p> : null}
          <div className="x-foot" style={{ marginTop: 4 }}>
            <button className="x-btn sm" type="button" onClick={() => setAdv(false)} disabled={advBusy}>
              Not now
            </button>
            <span className="sp" />
            <button className="x-btn p sm" type="button" onClick={sendAdv} disabled={advBusy}>
              {advBusy ? 'Saving…' : 'Ask an adviser to call'}
            </button>
          </div>
          <div className="x-fine">We save your details and this plan for the adviser.</div>
        </div>
      ) : (
        <div className="x-fabs">
          <button
            className={`x-fab mira ${miraOn ? 'on' : ''}${miraPaused ? ' paused' : ''}`}
            type="button"
            onClick={onMira}
            aria-pressed={!!miraOn}
            title={miraOn ? (miraPaused ? 'Resume Mira' : 'Pause Mira') : 'Have Mira talk you through this screen'}
          >
            {miraOn ? (miraPaused ? Ico.play : Ico.pause) : Ico.wand}
            <span>
              {miraOn
                ? miraPaused
                  ? 'Mira is paused — resume'
                  : 'Mira is speaking — pause'
                : 'Let Mira guide you (AI adviser)'}
            </span>
          </button>
          {advSent ? (
            <div className="x-fab done">
              {Ico.check}
              <span>We will be in touch on {advVia}.</span>
            </div>
          ) : (
            <button
              className="x-fab human"
              type="button"
              onClick={() => {
                setAdvEmail(session?.reportEmail || advEmail);
                setAdvPhone(session?.reportMobile || advPhone);
                setAdvErr('');
                setAdv(true);
              }}
              title="Leave a number or email for an adviser"
            >
              {Ico.chat}
              <span>Let me talk to a human adviser</span>
            </button>
          )}
        </div>
      )}
      {toast ? <div className="toast">{toast}</div> : null}
    </div>
  );
}
