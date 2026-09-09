import { type RefObject } from 'react';
import { D2C_ORDF, D2C_RDLBL, D2C_REQF } from '../../lib/catalog';
import { Ico } from '../../lib/icons';
import { parseSentence } from '../../lib/parse';
import { d2cReady, sessionAge, type GpSession } from '../../lib/types';

export function missing(session: GpSession) {
  const read = session.sentenceRead || {};
  const T = session.touched;
  const req: [string, string][] = [
    ['name', 'Name'],
    ['age', 'Age'],
    ['gender', 'Gender'],
    ['deps', 'Dependants'],
    ['res', 'Residency'],
    ['occ', 'Occupation'],
  ];
  const val: Record<string, string> = {
    name: session.name,
    age: session.age === '' ? '' : String(session.age),
    gender: session.gender,
    deps: session.depsChoice,
    res: session.residency,
    nat: session.nationality,
    occ: session.occupation,
  };
  return req
    .filter(r => !read[r[0]] && !T[r[0]])
    .map(r => ({ k: r[0], l: r[1], v: val[r[0]] || '', assumed: !!(val[r[0]] || '').trim() }));
}

export function confirmLine(session: GpSession): string {
  const rd = session.sentenceRead || {};
  const parts: string[] = [];
  if (rd.name) parts.push(rd.name);
  if (rd.age) parts.push(rd.age);
  if (rd.gender) parts.push(rd.gender);
  if (rd.res) parts.push(rd.res);
  if (rd.deps) parts.push(rd.deps === '1' ? '1 dependant' : `${rd.deps} dependants`);
  if (rd.occ) parts.push(rd.occ);
  const gaps: string[] = [];
  if (!String(session.name || '').trim()) gaps.push('name missing');
  if (!sessionAge(session)) gaps.push('age missing');
  if (!String(session.occupation || '').trim()) gaps.push('occupation missing');
  if (!parts.length && !gaps.length) return '';
  return parts.join(' · ') + (gaps.length ? ' — ' + gaps.join(', ') : '');
}

export function SentenceBody({
  session,
  listening,
  parsing,
  err,
  dictation,
  onSentence,
  onMic,
  boxRef,
}: {
  session: GpSession;
  listening: boolean;
  parsing: boolean;
  err: string;
  dictation: boolean;
  onSentence: (v: string) => void;
  onMic: () => void;
  boxRef?: RefObject<HTMLDivElement | null>;
}) {
  return (
    <>
      <div ref={boxRef} className="x-qwrap">
        <button
          type="button"
          className="x-qseed"
          aria-label="Fill sample sentence"
          onClick={() =>
            onSentence('my name is Michael · 42 years · Male · 2 dependants · Singapore Citizen · my job is a CEO')
          }
        />
        <div className={`x-qbox ${listening ? 'rec' : ''}`}>
        <textarea
          className="x-qta"
          rows={4}
          aria-label="Tell us about yourself in one sentence"
          placeholder="e.g. My name is Alex, 42, male Singapore citizen, married with two kids, working as a software engineer"
          value={session.sentence}
          onChange={e => onSentence(e.target.value)}
        />
        {dictation ? (
          <button
            className={`x-mic ${listening ? 'on' : ''}`}
            type="button"
            aria-pressed={listening}
            title={listening ? 'Stop dictating' : 'Dictate instead of typing'}
            onClick={onMic}
          >
            {listening ? Ico.stop : Ico.mic}
            <span>{listening ? 'Stop' : 'Speak'}</span>
          </button>
        ) : null}
        </div>
      </div>
      {listening ? (
        <div className="x-reclive">
          <i />
          <i />
          <i />
          <i />
          <i />
          <span>Listening — press Stop when you are done and we will fill in the details.</span>
        </div>
      ) : null}
      {err ? <div className="x-qerr">{err}</div> : null}
      <div className="x-live">{readPanel(session, parsing)}</div>
    </>
  );
}

function readPanel(session: GpSession, parsing: boolean) {
  const rd = session.sentenceRead;
  if (rd && Object.keys(rd).length && !session.sentenceDirty) {
    const miss = missing(session);
    const summary = confirmLine(session);
    const ready = d2cReady(session);
    const still = miss.length
      ? miss
      : [
          !String(session.name || '').trim() ? { k: 'name', l: 'Name', v: '', assumed: false } : null,
          !sessionAge(session) ? { k: 'age', l: 'Age', v: '', assumed: false } : null,
          !String(session.occupation || '').trim() ? { k: 'occ', l: 'Occupation', v: '', assumed: false } : null,
        ].filter((x): x is { k: string; l: string; v: string; assumed: boolean } => !!x);
    return (
      <div className={`x-qread ${session.sentenceAi ? 'ai' : ''}`}>
        <div className="x-qread-h">
          <b>
            {Ico.check} We captured
          </b>
          {session.sentenceAi ? (
            <em className="x-gtag">
              {Ico.wand}
              AI Verified
            </em>
          ) : null}
        </div>
        <div className="x-qchips">
          {Object.keys(rd).map(k => (
            <span key={k}>
              <em>{D2C_RDLBL[k] || k}</em>
              {rd[k]}
            </span>
          ))}
        </div>
        {summary ? <p className="x-qconfirm">{summary}</p> : null}
        {!ready ? (
          <div className="x-qneed">
            <b>Still needed</b>
            <div className="x-qchips xneed">
              {still.map(x => (
                <span key={x.k}>
                  <em>{x.l}</em>
                  {x.assumed ? (
                    <>
                      {x.v} <i>assumed</i>
                    </>
                  ) : (
                    <i>not set</i>
                  )}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div className="x-qdone">
            {Ico.check} Nothing else needed — you can continue
          </div>
        )}
      </div>
    );
  }
  if (session.sentence.trim().length < 6) return null;
  const got = parseSentence(session.sentence);
  const map: Record<string, string | undefined> = {
    name: got.name,
    age: got.age,
    gender: got.gender,
    deps: got.deps,
    res: got.res,
    occ: got.occ,
  };
  const have = D2C_ORDF.filter(k => map[k]);
  const miss = D2C_REQF.filter(k => !map[k]);
  return (
    <div className="x-livep">
      <b>
        <i className="dot" />
        {parsing ? 'Confirming' : 'Reading as you go'}
      </b>
      {have.length ? (
        <div className="x-qchips live">
          {have.map(k => (
            <span key={k}>
              <em>{D2C_RDLBL[k]}</em>
              {Ico.check}
            </span>
          ))}
        </div>
      ) : (
        <div className="x-livenone">Nothing recognised yet — keep going.</div>
      )}
      {miss.length ? (
        <div className="x-livemiss">
          <span>Still to say</span>
          {miss.map(k => (
            <em key={k}>{D2C_RDLBL[k]}</em>
          ))}
        </div>
      ) : (
        <div className="x-livedone">
          {Ico.check} {parsing ? 'Checking the details now' : 'Looks complete — we will fill this in when you pause'}
        </div>
      )}
    </div>
  );
}
