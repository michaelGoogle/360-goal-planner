import { useEffect, useRef, useState } from 'react';
import { CoachTour } from '../components/CoachTour';
import { ClassicToggle, Foot, SecHead } from '../components/ui';
import { parseAboutYou } from '../lib/api';
import { D2C_DOCS } from '../lib/catalog';
import { Ico } from '../lib/icons';
import { docSim, parsedToSession } from '../lib/local';
import { canDictate, startDictation } from '../lib/speech';
import { d2cReady, sessionAge, type DocKind, type GpSession } from '../lib/types';
import { DocTile } from './about/DocTile';
import { FormBody } from './about/FormBody';
import { missing, SentenceBody } from './about/SentenceBody';

export function AboutYou({
  session,
  onChange,
  onBack,
  onEstimate,
  busy,
  predictError,
  onToast,
  gtTtOn,
  onGtTtComplete,
}: {
  session: GpSession;
  onChange: (p: Partial<GpSession>) => void;
  onBack: () => void;
  onEstimate: () => void;
  busy: boolean;
  predictError?: string | null;
  onToast: (msg: string) => void;
  gtTtOn: boolean;
  onGtTtComplete: () => void;
}) {
  const recRef = useRef<{ stop: () => void } | null>(null);
  const sessionRef = useRef(session);
  const onChangeRef = useRef(onChange);
  const onToastRef = useRef(onToast);
  const abortRef = useRef<AbortController | null>(null);
  const skipDebounceRef = useRef(false);
  const sentenceBoxRef = useRef<HTMLDivElement>(null);
  const classicRef = useRef<HTMLSpanElement>(null);
  const [listening, setListening] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [err, setErr] = useState('');
  const dictation = canDictate();
  const age = sessionAge(session);
  const on = session.classic;
  const miss = missing(session);
  const blank = miss.filter(x => !x.assumed).map(x => x.l.toLowerCase());
  const formSummary = blank.length
    ? blank.join(', ') + ' still needed'
    : [session.name, age ? age + ' years' : null, session.gender, session.dependents + ' dependants', session.residency, session.occupation]
        .filter(Boolean)
        .join(' · ');
  const nDocs = Object.values(session.docs).filter(d => d && d.state === 'done').length;

  useEffect(() => {
    sessionRef.current = session;
    onChangeRef.current = onChange;
    onToastRef.current = onToast;
  }, [session, onChange, onToast]);

  useEffect(() => () => recRef.current?.stop(), []);

  const runExtract = async (t: string, opts?: { fromVoice?: boolean }) => {
    const text = t.trim();
    if (text.length < 6) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setParsing(true);
    setErr('');
    const fromVoice = !!opts?.fromVoice;
    try {
      const { fields: got, ai, llmError } = await parseAboutYou(text, ctrl.signal, {
        regexFallback: fromVoice ? false : undefined,
      });
      if (ctrl.signal.aborted) return;
      const cur = sessionRef.current;
      if (cur.classic || cur.sentence.trim() !== text) return;
      if (!Object.keys(got).length) {
        setErr(
          llmError ||
            (fromVoice
              ? 'We could not confirm what you said — try again, or open your details and fill them in.'
              : 'We could not read that. Try something like “My name is Alex, 42, male Singapore citizen, married with two kids, working as a software engineer” — or just open your details below and fill them in.'),
        );
        onChangeRef.current({ sentenceRead: null, sentenceDirty: false, sentenceAi: false });
        return;
      }
      const patch = parsedToSession(got);
      onChangeRef.current({ ...patch, sentenceAi: ai, touched: { ...cur.touched, ...patch.touched } });
      const n = Object.keys(got).length;
      if (llmError) {
        setErr(llmError + ' We filled what we could from the words.');
      }
      onToastRef.current('Filled ' + n + ' field' + (n > 1 ? 's' : '') + ' from what you said');
    } catch (e) {
      if (ctrl.signal.aborted || (e instanceof Error && e.name === 'AbortError')) return;
      setErr(
        fromVoice
          ? 'We could not confirm what you said — try again, or fill the form yourself.'
          : 'We could not confirm that just then — keep going, or fill the form yourself.',
      );
    } finally {
      if (!ctrl.signal.aborted) setParsing(false);
    }
  };

  useEffect(() => {
    if (session.classic || listening) return;
    if (skipDebounceRef.current) {
      skipDebounceRef.current = false;
      return;
    }
    const t = session.sentence.trim();
    if (t.length < 6 || !session.sentenceDirty) return;
    const id = window.setTimeout(() => {
      void runExtract(t);
    }, 2000);
    return () => {
      window.clearTimeout(id);
      abortRef.current?.abort();
      setParsing(false);
    };
  }, [session.classic, session.sentence, session.sentenceDirty, listening]);

  const toggleMic = () => {
    if (listening && recRef.current) {
      recRef.current.stop();
      return;
    }
    abortRef.current?.abort();
    const handle = startDictation({
      base: session.sentence,
      onLive: text => onChange({ sentence: text, sentenceDirty: true, sentenceAi: false }),
      onFinal: text => onChange({ sentence: text, sentenceDirty: true, sentenceAi: false }),
      onEnd: () => {
        recRef.current = null;
        const t = sessionRef.current.sentence.trim();
        if (t.length >= 6 && sessionRef.current.sentenceDirty) {
          skipDebounceRef.current = true;
          void runExtract(t, { fromVoice: true });
        }
        setListening(false);
      },
      onError: msg => {
        setListening(false);
        recRef.current = null;
        onToast(msg);
      },
    });
    if (!handle) {
      onToast('Dictation needs Chrome, Edge or Safari — type your sentence instead');
      return;
    }
    recRef.current = handle;
    setListening(true);
  };

  const onFile = (kind: DocKind, file: File | undefined) => {
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) {
      onToast('That file is over 8MB — try a photo or a smaller PDF');
      return;
    }
    onChange({ docs: { ...session.docs, [kind]: { name: file.name, state: 'reading', src: 'sim', v: {} } } });
    window.setTimeout(() => {
      onChange({
        docs: {
          ...session.docs,
          [kind]: { name: file.name, state: 'done', src: 'sim', v: docSim(kind, session) },
        },
      });
      onToast('Read — check the figures before you continue');
    }, 1100);
  };

  const touch = (k: string, p: Partial<GpSession>) => onChange({ ...p, touched: { ...session.touched, [k]: true } });

  return (
    <>
      <div className="x-h1 x-h1s">About you</div>
      <div className="x-lead">Say it, type it or upload it — whichever is quickest.</div>

      <div className="x-card x-quick">
        <SecHead
          n={1}
          title={on ? 'Your details' : 'Tell us in one sentence'}
          sub={on ? formSummary : ''}
          badge={
            <span ref={classicRef} className="x-coach-hit">
              <ClassicToggle on={on} onClick={() => onChange({ classic: !on })} />
            </span>
          }
        />
        <div className="x-pad x-secb">
          {on ? (
            <div ref={sentenceBoxRef}>
              <FormBody session={session} onTouch={touch} />
            </div>
          ) : (
            <SentenceBody
              session={session}
              listening={listening}
              parsing={parsing}
              err={err}
              dictation={dictation}
              onSentence={v => onChange({ sentence: v, sentenceDirty: true, sentenceAi: false })}
              onMic={toggleMic}
              boxRef={sentenceBoxRef}
            />
          )}
        </div>
      </div>

      <div className={`x-card x-sec ${session.docsOpen ? 'open' : ''}`}>
        <SecHead
          n={2}
          title="Add a document"
          sub={
            nDocs
              ? `${nDocs} document${nDocs > 1 ? 's' : ''} — your own figures will be used`
              : 'CPF statement, bank statement or policy — we read the figures for you'
          }
          open={session.docsOpen}
          onToggle={() => onChange({ docsOpen: !session.docsOpen })}
          badge={<em className="bd">OPTIONAL</em>}
        />
        {session.docsOpen ? (
          <div className="x-secb x-pad">
            <div className="x-doc3">
              {D2C_DOCS.map(row => (
                <DocTile
                  key={row[0]}
                  row={row}
                  doc={session.docs[row[0]]}
                  onFile={f => onFile(row[0], f)}
                  onDel={() => {
                    const docs = { ...session.docs };
                    delete docs[row[0]];
                    onChange({ docs });
                  }}
                  onVal={(field, val) => {
                    const cur = session.docs[row[0]];
                    if (!cur) return;
                    onChange({
                      docs: { ...session.docs, [row[0]]: { ...cur, v: { ...cur.v, [field]: val } } },
                    });
                  }}
                />
              ))}
            </div>
            <div className="x-docfoot">
              {nDocs ? (
                <span className="x-chip ok">
                  {Ico.check} {nDocs} document{nDocs > 1 ? 's' : ''} will be used
                </span>
              ) : (
                <span className="x-chip n">No documents yet — we will estimate instead</span>
              )}
              <span className="x-docpriv">Files are read to fill these fields and are not stored by this prototype.</span>
            </div>
          </div>
        ) : null}
      </div>

      {predictError ? <div className="x-qerr" style={{ marginBottom: 16 }}>{predictError}</div> : null}

      <CoachTour
        enabled={gtTtOn}
        onComplete={onGtTtComplete}
        steps={[
          {
            title: 'Tell us in one sentence',
            body: 'Type or speak a little about yourself — who you are, your age, family, job and residency. You do not need to add any numbers. We fill in the details from what you say.',
            anchorRef: sentenceBoxRef,
          },
          {
            title: 'Or enter data classically',
            body: 'Turn on Enter data classically to fill each field yourself, or to edit what we captured from your sentence.',
            anchorRef: classicRef,
          },
        ]}
      />

      <Foot>
        <button className="x-btn g" type="button" onClick={onBack}>
          ← Back
        </button>
        <span className="sp" />
        <button className="x-btn p" type="button" disabled={!d2cReady(session) || busy} onClick={onEstimate}>
          {busy ? 'Predicting…' : 'Predict my finance →'}
        </button>
      </Foot>
    </>
  );
}
