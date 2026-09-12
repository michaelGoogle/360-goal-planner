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

const FEMALE_HINT =
  /aria|jenny|sonia|libby|natasha|samantha|zira|hazel|susan|karen|moira|tessa|fiona|victoria|catherine|michelle|linda|eva|heera|veena|raveena|google uk english female|female/i;
const MALE_HINT = /male|david|mark|guy|davis|ryan|george|daniel|ravi|fred|tom|james/i;
const NATURAL_HINT = /natural|neural|online|premium|enhanced/i;

function scoreVoice(v: SpeechSynthesisVoice): number {
  const name = v.name.toLowerCase();
  const lang = (v.lang || '').toLowerCase();
  if (!lang.startsWith('en')) return -1;
  if (MALE_HINT.test(name) && !/female/.test(name)) return -1;
  let s = 10;
  if (NATURAL_HINT.test(name)) s += 100;
  if (FEMALE_HINT.test(name)) s += 50;
  if (name.includes('google') && /female|uk english female/.test(name)) s += 20;
  if (lang.startsWith('en-gb') || lang.startsWith('en-au') || lang.startsWith('en-sg')) s += 8;
  if (!v.localService) s += 12;
  return s;
}

function pickVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  let best: SpeechSynthesisVoice | null = null;
  let bestScore = 0;
  for (const v of voices) {
    const s = scoreVoice(v);
    if (s > bestScore) {
      bestScore = s;
      best = v;
    }
  }
  return best;
}

function startUtterance(text: string, voice: SpeechSynthesisVoice | null, onEnd?: () => void): void {
  const u = new SpeechSynthesisUtterance(text);
  if (voice) {
    u.voice = voice;
    u.lang = voice.lang;
  } else {
    u.lang = 'en-GB';
  }
  u.rate = 0.96;
  u.pitch = 1;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
}

export function speak(text: string, onEnd?: () => void): boolean {
  if (!('speechSynthesis' in window)) {
    onEnd?.();
    return false;
  }
  window.speechSynthesis.cancel();
  const voices = window.speechSynthesis.getVoices();
  if (voices.length) {
    startUtterance(text, pickVoice(voices), onEnd);
    return true;
  }
  let started = false;
  const kick = () => {
    if (started) return;
    started = true;
    startUtterance(text, pickVoice(window.speechSynthesis.getVoices()), onEnd);
  };
  window.speechSynthesis.addEventListener('voiceschanged', kick, { once: true });
  window.setTimeout(kick, 400);
  return true;
}

export function stopSpeak(): void {
  try {
    window.speechSynthesis.cancel();
  } catch {
    /* ignore */
  }
}

export function pauseSpeak(): boolean {
  try {
    if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
      window.speechSynthesis.pause();
      return true;
    }
  } catch {
    /* ignore */
  }
  return false;
}

export function resumeSpeak(): boolean {
  try {
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      return true;
    }
  } catch {
    /* ignore */
  }
  return false;
}
