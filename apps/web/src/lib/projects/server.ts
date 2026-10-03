import 'server-only';
import { randomUUID } from 'node:crypto';
import { createBackendClient } from '@f01/api-client';
import { validateEnvironment } from '../config/environment.mjs';
import { createInput, errors, states, type UpdateInput } from './contracts.ts';
import { backendCredentials, SessionUnavailable } from '../auth/session.ts';

type Environment = Record<string, string | undefined>;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function fail(code: string, status: number): Response {
  return Response.json({ error: { code, message: errors[code] ?? errors.INTERNAL_ERROR, request_id: randomUUID() } }, { status, headers: { 'Cache-Control': 'no-store' } });
}
export function configuration(env: Environment) {
  validateEnvironment(env);
  const base = new URL(env.API_INTERNAL_URL ?? '');
  const origin = new URL(env.NEXT_PUBLIC_APP_URL ?? 'http://127.0.0.1:3000');
  const token = (env.AUTH_MODE === 'oidc' ? env.AUTH_GATEWAY_TOKEN : env.DEV_API_TOKEN) ?? '';
  const local = ['localhost', '127.0.0.1', '[::1]'];
  for (const url of [base, origin]) if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('Invalid origin');
  if (token.length < 32 || /\s/.test(token) || (base.protocol === 'http:' && !local.includes(base.hostname)) || (env.AUTH_MODE !== 'oidc' && env.APP_ENV !== 'preview' && !local.includes(origin.hostname)) || (env.AUTH_MODE === 'oidc' && env.APP_ENV === 'production' && origin.protocol !== 'https:')) throw new Error('Invalid configuration');
  return { base, origin, token, local, authMode: env.AUTH_MODE ?? 'development' };
}
export function sameOrigin(request: Request, configured: URL, local: string[]) {
  try {
    const host = request.headers.get('host') ?? new URL(request.url).host;
    if (/[\s/\\?#@]/.test(host)) return false;
    const target = new URL(`${configured.protocol}//${host}`), origin = new URL(request.headers.get('origin') ?? '');
    return request.headers.get('sec-fetch-site') !== 'cross-site' && origin.origin === target.origin && (target.origin === configured.origin || (local.includes(target.hostname) && local.includes(configured.hostname) && target.port === configured.port));
  } catch { return false; }
}
export async function input(request: Request): Promise<unknown> {
  if (request.headers.get('content-type')?.split(';')[0] !== 'application/json') throw new Error('Invalid body');
  const reader = request.body?.getReader(); if (!reader) throw new Error('Missing body');
  let bytes = 0; const chunks: Uint8Array[] = [];
  try { for (;;) { const { value, done } = await reader.read(); if (done) break; bytes += value.byteLength; if (bytes > 128 * 1024) throw new Error('Large body'); chunks.push(value); } }
  finally { await reader.cancel().catch(() => undefined); }
  const result = new Uint8Array(bytes); let offset = 0; for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(result));
}
export const object = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
export async function handleProjectsRequest(request: Request, target: 'projects' | 'session' | 'usage', id: string | undefined, env: Environment, send: typeof fetch = fetch): Promise<Response> {
  let config: ReturnType<typeof configuration>;
  try { config = configuration(env); } catch { return fail('PROJECTS_NOT_CONFIGURED', 503); }
  const method = request.method;
  if ((target !== 'projects' && method !== 'GET') || (target === 'projects' && !['GET', id ? 'PATCH' : 'POST'].includes(method))) return fail('REQUEST_FORBIDDEN', 405);
  if (id && !uuid.test(id)) return fail('NOT_FOUND', 404);
  if (method !== 'GET' && !sameOrigin(request, config.origin, config.local)) return fail('REQUEST_FORBIDDEN', 403);

  const signal = AbortSignal.any([request.signal, AbortSignal.timeout(20000)]);
  try {
  const actor = await backendCredentials(request,config,send);
    const client = createBackendClient({ baseUrl: config.base.origin, bearerToken: actor.token, headers: actor.headers, fetch: send });
    let result;
    if (target === 'session') result = await client.GET('/v1/session', { signal });
    else if (target === 'usage') result = await client.GET('/v1/planning/usage', { signal });
    else if (method === 'GET' && id) result = await client.GET('/v1/projects/{project_id}', { params: { path: { project_id: id } }, signal });
    else if (method === 'GET') {
      const params = new URL(request.url).searchParams;
      const status = params.get('status'), q = params.get('q') ?? '', cursor = params.get('cursor'), archived = params.get('archived') ?? 'false';
      if ((status && !states.includes(status as typeof states[number])) || q.length > 100 || (cursor?.length ?? 0) > 500 || !['true', 'false'].includes(archived)) return fail('VALIDATION_ERROR', 422);
      result = await client.GET('/v1/projects', { params: { query: { q, status: status as typeof states[number] | undefined || undefined, archived: archived === 'true', cursor: cursor ?? undefined, limit: 20 } }, signal });
    } else {
      let body: unknown; try { body = await input(request); } catch { return fail('VALIDATION_ERROR', 422); }
      if (!object(body)) return fail('VALIDATION_ERROR', 422);
      if (method === 'POST') {
        if (Object.keys(body).some(key => !['title', 'brief'].includes(key)) || typeof body.brief !== 'string' || (body.title != null && typeof body.title !== 'string')) return fail('VALIDATION_ERROR', 422);
        const data = createInput((body.title as string | null) ?? '', body.brief);
        const key = request.headers.get('idempotency-key');
        if (!data || !key || !/^[A-Za-z0-9._:-]{1,200}$/.test(key)) return fail('VALIDATION_ERROR', 422);
        result = await client.POST('/v1/projects', { body: data, params: { header: { 'idempotency-key': key } }, signal });
      } else {
        if (!Object.keys(body).length || Object.keys(body).some(key => !['title', 'archived'].includes(key)) || ('title' in body && (typeof body.title !== 'string' || !body.title.trim() || Array.from(body.title.trim()).length > 100)) || ('archived' in body && typeof body.archived !== 'boolean')) return fail('VALIDATION_ERROR', 422);
        const etag = request.headers.get('if-match'); if (!etag || !new RegExp(`^"project-${id}-m[1-9][0-9]*"$`).test(etag)) return fail('METADATA_CONFLICT', 428);
        result = await client.PATCH('/v1/projects/{project_id}', { params: { path: { project_id: id! }, header: { 'if-match': etag } }, body: body as UpdateInput, signal });
      }
    }
    if (!result.response.ok) {
      const code = object(result.error) && object(result.error.error) && typeof result.error.error.code === 'string' ? result.error.error.code : 'INTERNAL_ERROR';
      return fail(code in errors ? code : 'INTERNAL_ERROR', result.response.status >= 500 ? 503 : result.response.status);
    }
    const serialized = JSON.stringify(result.data);
    if (!serialized || serialized.includes(config.token)) return fail('INTERNAL_ERROR', 502);
    const headers: Record<string, string> = { 'Cache-Control': 'no-store' };
    const etag = result.response.headers.get('etag'); if (etag && /^"project-[0-9a-f-]+-m[1-9][0-9]*"$/i.test(etag)) headers.ETag = etag;
    return Response.json(result.data, { status: result.response.status, headers });
  } catch (error) { return fail(error instanceof SessionUnavailable && error.status===401 ? 'AUTHENTICATION_REQUIRED' : 'SERVICE_UNAVAILABLE',error instanceof SessionUnavailable ? error.status : 503); }
}
