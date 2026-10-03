import { backendCredentials, SessionUnavailable } from '../auth/session.ts';
import 'server-only';
import { createBackendClient } from '@f01/api-client';
import { configuration, sameOrigin, input, fail, object } from '../projects/server.ts';
import { errors } from '../projects/contracts.ts';
import { uuid } from './contracts.ts';
export type RunResource = 'runs' | 'run' | 'cancel' | 'retry' | 'deployments';
export async function handleRunRequest(request: Request, projectId: string, resource: RunResource, env: Record<string,string|undefined>, runId?: string, send: typeof fetch = fetch): Promise<Response> {
  if (!uuid.test(projectId) || (runId && !uuid.test(runId))) return fail('NOT_FOUND',404);
  const write = resource === 'cancel' || resource === 'retry' || (resource === 'runs' && request.method === 'POST');
  if (request.method !== (write ? 'POST' : 'GET') || (['run','cancel','retry'].includes(resource) && !runId)) return fail('REQUEST_FORBIDDEN',405);
  let config: ReturnType<typeof configuration>;
  try { config = configuration(env); } catch { return fail('PROJECTS_NOT_CONFIGURED',503); }
  if (write && !sameOrigin(request,config.origin,config.local)) return fail('REQUEST_FORBIDDEN',403);

  const path = { project_id:projectId }, runPath = { ...path, run_id:runId! }, signal = AbortSignal.any([request.signal,AbortSignal.timeout(20000)]);
  const params = new URL(request.url).searchParams, cursor = params.get('cursor') ?? undefined;
  if ((cursor?.length ?? 0) > 500) return fail('VALIDATION_ERROR',422);
  try {
  const actor = await backendCredentials(request,config,send);
    const client = createBackendClient({ baseUrl:config.base.origin, bearerToken:actor.token, headers:actor.headers, fetch:send });
    let result;
    if (write) {
      let body: unknown; try { body = await input(request); } catch { return fail('VALIDATION_ERROR',422); }
      if (!object(body)) return fail('VALIDATION_ERROR',422);
      const key = request.headers.get('idempotency-key');
      if (resource !== 'cancel' && (!key || !/^[A-Za-z0-9._:-]{1,200}$/.test(key))) return fail('VALIDATION_ERROR',422);
      if (resource === 'runs') {
        if (Object.keys(body).some(k => !['request_id','expected_brain_revision_id'].includes(k)) || typeof body.request_id !== 'string' || !uuid.test(body.request_id) || typeof body.expected_brain_revision_id !== 'string' || !uuid.test(body.expected_brain_revision_id)) return fail('VALIDATION_ERROR',422);
        result = await client.POST('/v1/projects/{project_id}/runs',{params:{path,header:{'idempotency-key':key!}},body:{request_id:body.request_id,expected_brain_revision_id:body.expected_brain_revision_id},signal});
      } else {
        if (Object.keys(body).length) return fail('VALIDATION_ERROR',422);
        result = resource === 'cancel' ? await client.POST('/v1/projects/{project_id}/runs/{run_id}/cancel',{params:{path:runPath},body:{},signal}) : await client.POST('/v1/projects/{project_id}/runs/{run_id}/retry',{params:{path:runPath,header:{'idempotency-key':key!}},body:{},signal});
      }
    } else if (resource === 'run') result = await client.GET('/v1/projects/{project_id}/runs/{run_id}',{params:{path:runPath},signal});
    else if (resource === 'deployments') result = await client.GET('/v1/projects/{project_id}/deployments',{params:{path,query:{cursor,limit:20}},signal});
    else result = await client.GET('/v1/projects/{project_id}/runs',{params:{path,query:{cursor,limit:20}},signal});
    if (!result.response.ok) {
      const code = object(result.error) && object(result.error.error) && typeof result.error.error.code === 'string' ? result.error.error.code : 'INTERNAL_ERROR';
      return fail(code in errors ? code : 'INTERNAL_ERROR',result.response.status >= 500 ? 503 : result.response.status);
    }
    if (JSON.stringify(result.data)?.includes(config.token)) return fail('INTERNAL_ERROR',502);
    return Response.json(result.data,{status:result.response.status,headers:{'Cache-Control':'no-store'}});
  } catch (error) { return fail(error instanceof SessionUnavailable && error.status===401 ? 'AUTHENTICATION_REQUIRED' : 'SERVICE_UNAVAILABLE',error instanceof SessionUnavailable ? error.status : 503); }
}
export async function handleEventStream(request: Request, projectId: string, env: Record<string,string|undefined>, send: typeof fetch = fetch): Promise<Response> {
  if (!uuid.test(projectId)) return fail('NOT_FOUND',404);
  if (request.method !== 'GET') return fail('REQUEST_FORBIDDEN',405);
  let config: ReturnType<typeof configuration>;
  try { config = configuration(env); } catch { return fail('PROJECTS_NOT_CONFIGURED',503); }
  const header = request.headers.get('last-event-id'), after = header ?? new URL(request.url).searchParams.get('after_sequence') ?? '0';
  if (!/^[0-9]{1,10}$/.test(after) || Number(after) > 2147483647) return fail('VALIDATION_ERROR',422);
  try {
    const actor = await backendCredentials(request,config,send);
    const client = createBackendClient({baseUrl:config.base.origin,bearerToken:actor.token,headers:actor.headers,fetch:send});
    const result = await client.GET('/v1/projects/{project_id}/events/stream',{params:{path:{project_id:projectId},query:{after_sequence:after},header:{'last-event-id':header ?? undefined}},parseAs:'stream',signal:request.signal});
    if (!result.response.ok) return fail(result.response.status === 401 ? 'AUTHENTICATION_REQUIRED' : result.response.status === 404 ? 'NOT_FOUND' : result.response.status === 422 ? 'VALIDATION_ERROR' : 'SERVICE_UNAVAILABLE',result.response.status);
    if (!result.data || !result.response.headers.get('content-type')?.startsWith('text/event-stream')) return fail('SERVICE_UNAVAILABLE',502);
    return new Response(result.data,{headers:{'Content-Type':'text/event-stream','Cache-Control':'no-store','X-Accel-Buffering':'no'}});
  } catch (error) { return fail(error instanceof SessionUnavailable && error.status===401 ? 'AUTHENTICATION_REQUIRED' : 'SERVICE_UNAVAILABLE',error instanceof SessionUnavailable ? error.status : 503); }
}
