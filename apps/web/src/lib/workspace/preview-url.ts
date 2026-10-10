import {uuid} from './contracts.ts';
export function isolatedPreviewPath(value: string, expires: string, factoryHost?: string): string | null {
  try {
    const url = new URL(value), expiry = Date.parse(expires), parts = url.pathname.split('/');
    const host = factoryHost ?? (typeof window !== 'undefined' ? window.location.hostname : undefined);
    if (!Number.isFinite(expiry) || expiry <= Date.now() || url.username || url.password || url.search || url.hash || parts.length !== 5 || parts[1] !== 'p' || !uuid.test(parts[2] ?? '') || !/^[A-Za-z0-9_-]{43}$/.test(parts[3] ?? '') || parts[4] !== '' || url.hostname === host) return null;
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))) return null;
    return url.href;
  } catch { return null; }
}

/** A separate top-level loopback origin; never use this URL as an iframe source. */
export function isolatedBrowserPath(value: string | null | undefined, embedded: string, expires: string, projectId: string, factoryHost?: string): string | null {
  try {
    const host = factoryHost ?? (typeof window !== 'undefined' ? window.location.hostname : undefined);
    if (!value || host !== '127.0.0.1' || !uuid.test(projectId) || !isolatedPreviewPath(embedded, expires, host)) return null;
    const source = new URL(embedded), url = new URL(value);
    if (source.protocol !== 'http:' || source.hostname !== 'localhost' || url.protocol !== 'http:' || url.hostname !== `f01-${projectId.replaceAll('-', '').toLowerCase()}.localhost` || url.port !== source.port || url.pathname !== source.pathname || url.username || url.password || url.search || url.hash) return null;
    return url.href;
  } catch { return null; }
}
