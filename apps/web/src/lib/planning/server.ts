import 'server-only';
import { randomUUID } from 'node:crypto';
import { validateEnvironment } from '../config/environment.mjs';
import { isErrorCode, isProjectPlan, parseIdea, planningErrors, record, type PlanningErrorCode } from './contracts.ts';
import { backendCredentials, SessionUnavailable } from '../auth/session.ts';

const REQUEST_LIMIT = 128 * 1024;
const RESPONSE_LIMIT = 256 * 1024;
const DEADLINE_MS = 130_000;
type Environment = Record<string, string | undefined>;
type Fetch = typeof fetch;
class BodyLimitError extends Error {}

function failure(code: PlanningErrorCode, requestId: string = randomUUID()): Response {
  const error = planningErrors[code];
  return Response.json({ error: { code, message: error.message, request_id: requestId } }, {
    status: error.status, headers: { 'Cache-Control': 'no-store', 'X-Request-ID': requestId },
  });
}

async function boundedText(stream: ReadableStream<Uint8Array> | null, limit: number): Promise<string> {
  if (!stream) throw new Error('Invalid body');
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) throw new BodyLimitError();
      chunks.push(value);
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }
  const data = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { data.set(chunk, offset); offset += chunk.byteLength; }
  return new TextDecoder('utf-8', { fatal: true }).decode(data);
}

function serverConfiguration(env: Environment): { endpoint: string; token: string; origin: URL } | null {
  try {
    validateEnvironment(env);
    const api = new URL(env.API_INTERNAL_URL ?? '');
    const origin = new URL(env.NEXT_PUBLIC_APP_URL ?? 'http://127.0.0.1:3000');
    const token = (env.AUTH_MODE === 'oidc' ? env.AUTH_GATEWAY_TOKEN : env.DEV_API_TOKEN) ?? '';
    const loopback = ['localhost', '127.0.0.1', '[::1]'];
    if (token.length < 32 || /\s/.test(token) || api.username || api.password || api.search || api.hash || api.pathname !== '/') return null;
    if (!['http:', 'https:'].includes(api.protocol) || (api.protocol === 'http:' && !loopback.includes(api.hostname))) return null;
    if (origin.username || origin.password || origin.search || origin.hash || origin.pathname !== '/' || !['http:', 'https:'].includes(origin.protocol)) return null;
    if (env.AUTH_MODE !== 'oidc' && (env.APP_ENV ?? 'development') !== 'preview' && !loopback.includes(origin.hostname)) return null;
    if (env.AUTH_MODE === 'oidc' && env.APP_ENV === 'production' && origin.protocol !== 'https:') return null;
    return { endpoint: new URL('/v1/plan', api).href, token, origin };
  } catch { return null; }
}

function isSameOrigin(request: Request, configured: URL): boolean {
  try {
    const origin = new URL(request.headers.get('origin') ?? '');
    // Next.js can normalize request.url to localhost; validate the actual HTTP Host.
    const host = request.headers.get('host') ?? new URL(request.url).host;
    if (/[\s/\\?#@]/.test(host)) return false;
    const target = new URL(`${configured.protocol}//${host}`);
    if (origin.origin !== target.origin || request.headers.get('sec-fetch-site') === 'cross-site') return false;
    if (target.origin === configured.origin) return true;
    // Local users may open localhost or 127.0.0.1, but keep the configured scheme and port.
    const loopback = ['localhost', '127.0.0.1', '[::1]'];
    return loopback.includes(target.hostname) && loopback.includes(configured.hostname)
      && target.protocol === configured.protocol && target.port === configured.port;
  } catch { return false; }
}

export async function handlePlanRequest(request: Request, env: Environment, send: Fetch = fetch): Promise<Response> {
  const configuration = serverConfiguration(env);
  if (!configuration) return failure('PLANNING_NOT_CONFIGURED');
  if (!isSameOrigin(request, configuration.origin)) return failure('REQUEST_FORBIDDEN');
  if (request.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase() !== 'application/json') return failure('UNSUPPORTED_MEDIA_TYPE');
  if (Number(request.headers.get('content-length')) > REQUEST_LIMIT) return failure('REQUEST_TOO_LARGE');
  let input: unknown;
  try { input = JSON.parse(await boundedText(request.body, REQUEST_LIMIT)); }
  catch (error) { return failure(error instanceof BodyLimitError ? 'REQUEST_TOO_LARGE' : 'VALIDATION_ERROR'); }
  const idea = parseIdea(input);
  if (!idea) return failure('VALIDATION_ERROR');

  const deadline = AbortSignal.timeout(DEADLINE_MS);
  try {
    const actor=await backendCredentials(request,{base:new URL(new URL(configuration.endpoint).origin),origin:configuration.origin,token:configuration.token,authMode:env.AUTH_MODE ?? 'development'},send);
    const response = await send(configuration.endpoint, {
      method: 'POST', redirect: 'error', cache: 'no-store',
      headers: { ...actor.headers, 'Content-Type': 'application/json', Authorization: `Bearer ${actor.token}` },
      body: JSON.stringify({ idea }), signal: AbortSignal.any([deadline, request.signal]),
    });
    let body: string;
    try { body = await boundedText(response.body, RESPONSE_LIMIT); }
    catch { return failure('PROVIDER_INVALID_RESPONSE'); }
    // Treat the upstream as untrusted: never relay credentials, raw errors, or headers.
    if (body.includes(configuration.token) || body.includes(actor.token)) return failure('PROVIDER_INVALID_RESPONSE');
    let payload: unknown;
    try { payload = JSON.parse(body); } catch { return failure('PROVIDER_INVALID_RESPONSE'); }
    if (!response.ok) {
      const error = record(payload) && record(payload.error) ? payload.error : null;
      if(env.AUTH_MODE==='oidc'&&response.status===401)return Response.json({error:{code:'AUTHENTICATION_REQUIRED',message:'Sign in again to make a plan.',request_id:randomUUID()}},{status:401,headers:{'Cache-Control':'no-store'}});
      const code = error && isErrorCode(error.code) ? error.code : 'PROVIDER_ERROR';
      const requestId = error && typeof error.request_id === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(error.request_id) ? error.request_id : undefined;
      return failure(code, requestId);
    }
    if (!isProjectPlan(payload)) return failure('PROVIDER_INVALID_RESPONSE');
    return Response.json(payload, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    if(error instanceof SessionUnavailable)return Response.json({error:{code:'AUTHENTICATION_REQUIRED',message:'Sign in to make a plan.',request_id:randomUUID()}},{status:error.status,headers:{'Cache-Control':'no-store'}});
    return failure(deadline.aborted ? 'PROVIDER_TIMEOUT' : 'PROVIDER_UNAVAILABLE');
  }
}
