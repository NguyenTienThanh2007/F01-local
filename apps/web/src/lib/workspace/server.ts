import { backendCredentials, SessionUnavailable } from '../auth/session.ts';
import 'server-only';
import { createBackendClient } from '@f01/api-client';
import { configuration, sameOrigin, input, fail, object } from '../projects/server.ts';
import { errors } from '../projects/contracts.ts';
import { changeInput, uuid } from './contracts.ts';
export type Resource = 'workspace' | 'brain' | 'brain/revisions' | 'requests' | 'events' | 'versions';
export async function handleWorkspaceRequest(request: Request, projectId: string, resource: Resource, env: Record<string, string | undefined>, versionId?: string, send: typeof fetch = fetch): Promise<Response> {
  if (!uuid.test(projectId) || (versionId && !uuid.test(versionId))) return fail('NOT_FOUND', 404);
  if (request.method !== 'GET' && !(resource === 'requests' && request.method === 'POST')) return fail('REQUEST_FORBIDDEN', 405);
  let config: ReturnType<typeof configuration>;
  try { config = configuration(env); } catch { return fail('PROJECTS_NOT_CONFIGURED', 503); }
  if (request.method === 'POST' && !sameOrigin(request, config.origin, config.local)) return fail('REQUEST_FORBIDDEN', 403);

  const signal = AbortSignal.any([request.signal, AbortSignal.timeout(20000)]);
  const params = new URL(request.url).searchParams, cursor = params.get('cursor') ?? undefined;
  const runId = params.get('run_id') ?? undefined;
  if (runId && !uuid.test(runId)) return fail('VALIDATION_ERROR', 422);
  const revision = params.get('revision'), after = params.get('after_sequence') ?? '0';
  if ((cursor?.length ?? 0) > 500 || (revision !== null && (!/^[1-9][0-9]*$/.test(revision) || Number(revision) > 2147483647)) || !/^[0-9]+$/.test(after) || Number(after) > 2147483647) return fail('VALIDATION_ERROR', 422);
  const path = { project_id: projectId }, query = { cursor, limit: 20 };
  try {
  const actor = await backendCredentials(request,config,send);
    const client = createBackendClient({ baseUrl: config.base.origin, bearerToken: actor.token, headers: actor.headers, fetch: send });
    let result;
    if (request.method === 'POST') {
      let body: unknown; try { body = await input(request); } catch { return fail('VALIDATION_ERROR', 422); }
      if (!object(body) || Object.keys(body).some(k => !['text', 'base_brain_revision_id', 'base_version_id'].includes(k)) || typeof body.text !== 'string' || typeof body.base_brain_revision_id !== 'string' || !(body.base_version_id === null || typeof body.base_version_id === 'string')) return fail('VALIDATION_ERROR', 422);
      const data = changeInput(body.text, body.base_brain_revision_id, body.base_version_id);
      const key = request.headers.get('idempotency-key');
      if (!data || !key || !/^[A-Za-z0-9._:-]{1,200}$/.test(key)) return fail('VALIDATION_ERROR', 422);
      result = await client.POST('/v1/projects/{project_id}/requests', { params: { path, header: { 'idempotency-key': key } }, body: data, signal });
    } else if (resource === 'workspace') result = await client.GET('/v1/projects/{project_id}/workspace', { params: { path }, signal });
    else if (resource === 'brain') result = await client.GET('/v1/projects/{project_id}/brain', { params: { path, query: { revision: revision ? Number(revision) : undefined } }, signal });
    else if (resource === 'brain/revisions') result = await client.GET('/v1/projects/{project_id}/brain/revisions', { params: { path, query }, signal });
    else if (resource === 'requests') result = await client.GET('/v1/projects/{project_id}/requests', { params: { path, query }, signal });
    else if (resource === 'events') result = await client.GET('/v1/projects/{project_id}/events', { params: { path, query: { after_sequence: Number(after), limit: 20, run_id: runId } }, signal });
    else if (versionId) result = await client.GET('/v1/projects/{project_id}/versions/{version_id}', { params: { path: { ...path, version_id: versionId } }, signal });
    else result = await client.GET('/v1/projects/{project_id}/versions', { params: { path, query }, signal });
    if (!result.response.ok) {
      const code = object(result.error) && object(result.error.error) && typeof result.error.error.code === 'string' ? result.error.error.code : 'INTERNAL_ERROR';
      return fail(code in errors ? code : 'INTERNAL_ERROR', result.response.status >= 500 ? 503 : result.response.status);
    }
    const serialized = JSON.stringify(result.data);
    if (!serialized || serialized.includes(config.token)) return fail('INTERNAL_ERROR', 502);
    return Response.json(result.data, { status: result.response.status, headers: { 'Cache-Control': 'no-store' } });
  } catch (error) { return fail(error instanceof SessionUnavailable && error.status===401 ? 'AUTHENTICATION_REQUIRED' : 'SERVICE_UNAVAILABLE',error instanceof SessionUnavailable ? error.status : 503); }
}
