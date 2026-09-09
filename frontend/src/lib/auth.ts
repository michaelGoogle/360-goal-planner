/** Shared console auth against FM (portal hash handoff). */

export const AUTH_STORAGE_KEY = 'siriheritage.consoleAuth';

export interface AuthSession {
  access_token: string;
  user: { id: string; email: string; display_name: string | null };
}

export function loadAuthSession(): AuthSession | null {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed?.access_token) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveAuthSession(session: AuthSession): void {
  sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

const AUTH_HANDOFF_PREFIX = 'siriheritage_auth=';

export async function consumeAuthHandoff(): Promise<AuthSession | null> {
  if (typeof window === 'undefined') return null;
  const hash = window.location.hash.replace(/^#/, '');
  if (!hash.startsWith(AUTH_HANDOFF_PREFIX)) return null;
  const token = decodeURIComponent(hash.slice(AUTH_HANDOFF_PREFIX.length));
  history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
  if (!token) return null;

  const host = window.location.hostname;
  const isSynology = host === 'mgzh11.synology.me' || host.endsWith('.synology.me');
  const bases = ['/fm'];
  if (isSynology) bases.push(`https://${host}:8462`);
  else bases.push('http://127.0.0.1:8062', 'http://127.0.0.1:8003');

  for (const base of bases) {
    try {
      const res = await fetch(`${base}/v1/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) continue;
      const user = (await res.json()) as AuthSession['user'];
      const session = { access_token: token, user };
      saveAuthSession(session);
      return session;
    } catch {
      /* try next */
    }
  }
  return null;
}

export function suitePortalUrl(): string {
  const host = window.location.hostname;
  const isSynology = host === 'mgzh11.synology.me' || host.endsWith('.synology.me');
  const proto = isSynology ? 'https:' : window.location.protocol;
  const port = isSynology ? 8460 : 8060;
  return `${proto}//${host}:${port}/`;
}
