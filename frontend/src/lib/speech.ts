type Rec = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((ev: { resultIndex: number; results: Array<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onerror: ((ev: { error?: string }) => void) | null;
  onend: (() => void) | null;
};

export function canDictate(): boolean {
  const w = window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };
  return !!(w.SpeechRecognition || w.webkitSpeechRecognition);
}

export function startDictation(opts: {
  onLive: (text: string) => void;
  onFinal: (text: string) => void;
  onEnd: () => void;
  onError: (msg: string) => void;
  base: string;
}): { stop: () => void } | null {
  const w = window as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec };
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Ctor) return null;
  let rec: Rec;
  try {
    rec = new Ctor();
  } catch {
    opts.onError('Could not start the microphone');
    return null;
  }
  rec.lang = 'en-SG';
  rec.continuous = true;
  rec.interimResults = true;
  let base = opts.base;
  rec.onresult = ev => {
    let fin = '';
    let int = '';
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const tr = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) fin += tr;
      else int += tr;
    }
    if (fin) base = (base ? base.replace(/\s+$/, '') + ' ' : '') + fin.trim();
    opts.onFinal(base);
    opts.onLive((base + (int ? ' ' + int : '')).trim());
  };
  rec.onerror = ev => {
    opts.onError(
      ev && ev.error === 'not-allowed'
        ? 'Microphone blocked — allow it in your browser to dictate'
        : 'We did not catch that — try again',
    );
  };
  rec.onend = () => opts.onEnd();
  try {
    rec.start();
  } catch {
    opts.onError('Could not start the microphone');
    return null;
  }
  return { stop: () => rec.stop() };
}

export function speak(text: string, onEnd?: () => void): boolean {
  if (!('speechSynthesis' in window)) {
    onEnd?.();
    return false;
  }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'en-SG';
  u.rate = 1;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
  return true;
}

export function stopSpeak(): void {
  try {
    window.speechSynthesis.cancel();
  } catch {
    /* ignore */
  }
}
