import { useEffect, useState } from 'react';
import { Ico } from '../../lib/icons';
import { postJson, type CrmSyncResponse } from '../../lib/api';
import type { GpSession } from '../../lib/types';

export function ReportNotify({
  session,
  pre,
  post,
  onClose,
  onToast,
  onShared,
}: {
  session: GpSession;
  pre: number | null;
  post: number | null;
  onClose: () => void;
  onToast: (msg: string) => void;
  onShared: (p: {
    mobile: string;
    email: string;
    jobId: string;
    contactId?: string;
    planId?: string;
  }) => void;
}) {
  const [email, setEmail] = useState(session.reportEmail || '');
  const [mobile, setMobile] = useState(session.reportMobile || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const send = () => {
    const em = email.trim();
    const ph = mobile.trim();
    if (ph.replace(/\D/g, '').length < 8) {
      setErr('Enter a mobile number');
      return;
    }
    if (!em || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) {
      setErr('Enter an email address');
      return;
    }
    setErr('');
    setBusy(true);
    const payload = { email: em, mobile: ph, pre, post, session };
    void (async () => {
      let contactId = session.insapiContactId || '';
      let planId = session.insapiPlanId || '';
      try {
        const crm = await postJson<CrmSyncResponse>('/v1/crm-sync', payload);
        contactId = crm.contactId || contactId;
        planId = crm.planId || planId;
      } catch {
        onToast('Could not save the plan to the adviser CRM. We will still send the report.');
      }
      const data = await postJson<{ success: boolean; jobId: string }>('/v1/video-notify', {
        ...payload,
        session: { ...session, reportEmail: em, reportMobile: ph, insapiContactId: contactId, insapiPlanId: planId },
      });
      onShared({ mobile: ph, email: em, jobId: data.jobId, contactId, planId });
      onToast('We will send a link when the report video is ready');
      onClose();
    })().catch(e => {
      setBusy(false);
      setErr(e instanceof Error && e.message ? e.message : 'Could not start the video');
    });
  };

  return (
    <div className="x-advp x-rpt-notify" role="dialog" aria-label="Share report">
      <button className="cl" type="button" onClick={onClose} aria-label="Close">
        {Ico.close}
      </button>
      <b>Share report</b>
      <p>
        Enter a mobile number and email so we can WhatsApp a link, keep one report per customer, and
        save the plan for an adviser.
      </p>
      <div className="x-f">
        <label htmlFor="rpt-phone">Mobile</label>
        <input
          id="rpt-phone"
          className="x-in"
          value={mobile}
          type="tel"
          placeholder="+65 8123 4567"
          autoComplete="tel"
          disabled={busy}
          onChange={e => setMobile(e.target.value)}
        />
      </div>
      <div className="x-f">
        <label htmlFor="rpt-email">Email</label>
        <input
          id="rpt-email"
          className="x-in"
          value={email}
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          disabled={busy}
          onChange={e => setEmail(e.target.value)}
        />
      </div>
      {err ? <p className="x-ferr">{err}</p> : null}
      <div className="x-foot" style={{ marginTop: 4 }}>
        <button className="x-btn sm" type="button" onClick={onClose} disabled={busy}>
          Not now
        </button>
        <span className="sp" />
        <button className="x-btn p sm" type="button" onClick={send} disabled={busy}>
          {busy ? 'Sending…' : 'Share report'}
        </button>
      </div>
    </div>
  );
}
