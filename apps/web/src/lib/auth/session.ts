import 'server-only';
type Config = { base: URL; origin: URL; token: string; authMode: string };
export class SessionUnavailable extends Error { status:number;constructor(status = 401) { super('Authenticated session unavailable.');this.status=status; } }
export function cookieNames(origin: URL) { const prefix = origin.protocol === 'https:' ? '__Host-f01-' : 'f01-local-'; return { session: prefix+'session', csrf: prefix+'csrf', login: prefix+'login' }; }
export function readCookie(request: Request, name: string) {
  const values = (request.headers.get('cookie') ?? '').split(';').map(part=>part.trim()).filter(part=>part.startsWith(name+'='));
  if (values.length !== 1) return '';
  const value=values[0]!.slice(name.length+1); return /^[A-Za-z0-9_-]{40,100}$/.test(value) ? value : '';
}
export async function backendCredentials(request: Request, config: Config, send: typeof fetch) {
  if (config.authMode !== 'oidc') return { token: config.token, headers: {} as Record<string,string> };
  const names=cookieNames(config.origin), session=readCookie(request,names.session), csrf=readCookie(request,names.csrf);
  if (!session || !csrf) throw new SessionUnavailable();
  let response: Response;
  try { response=await send(new URL('/v1/auth/access',config.base),{method:'POST',redirect:'error',cache:'no-store',headers:{Authorization:`Bearer ${config.token}`,'Content-Type':'application/json'},body:JSON.stringify({session,csrf}),signal:AbortSignal.any([request.signal,AbortSignal.timeout(10000)])}); }
  catch { throw new SessionUnavailable(503); }
  if (!response.ok) throw new SessionUnavailable(response.status===401 ? 401 : 503);
  const body=await response.text(); if(body.length>20000)throw new SessionUnavailable();
  const result: unknown=JSON.parse(body);
  if(!result || typeof result!=='object' || !('access_token' in result) || typeof result.access_token!=='string' || result.access_token.length>16384 || !/^[A-Za-z0-9_.-]+$/.test(result.access_token))throw new SessionUnavailable();
  return {token:result.access_token,headers:{'X-F01-Session':session,'X-F01-CSRF':csrf}};
}
