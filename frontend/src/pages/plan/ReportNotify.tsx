import { useEffect, useState } from 'react';
import { Ico } from '../../lib/icons';
import { postJson } from '../../lib/api';
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
  onShared: (p: { mobile: string; email: string; jobId: string }) => void;
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
    if (em && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) {
      setErr('Check the email address');
      return;
    }
    setErr('');
    setBusy(true);
    void postJson<{ success: boolean; jobId: string }>('/v1/video-notify', {
      email: em,
      mobile: ph,
      pre,
      post,
      session,
    })
      .then(data => {
        onShared({ mobile: ph, email: em, jobId: data.jobId });
        onToast('We will send a link when the report video is ready');
        onClose();
      })
      .catch(e => {
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
        Enter a mobile number so we can WhatsApp a link and keep one report per customer. Email is
        optional.
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
        <label htmlFor="rpt-email">
          Email <span className="op">optional</span>
        </label>
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
