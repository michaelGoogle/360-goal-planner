const KEY = 'gp.gtTt';
const LEGACY = 'gp.aboutYouHelp';

function readRaw(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

/** First visit: on. After the tour is finished: off. Manual toggle writes on/off. */
export function readGtTt(): boolean {
  const raw = readRaw();
  if (raw === 'on') return true;
  if (raw === 'off') return false;
  try {
    if (sessionStorage.getItem(LEGACY) === '1') {
      writeGtTt(false);
      sessionStorage.removeItem(LEGACY);
      return false;
    }
  } catch {
    /* private mode */
  }
  return true;
}

export function writeGtTt(on: boolean) {
  try {
    localStorage.setItem(KEY, on ? 'on' : 'off');
  } catch {
    /* private mode */
  }
}
