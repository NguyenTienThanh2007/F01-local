import test from 'node:test';
import assert from 'node:assert/strict';
import { handleProjectsRequest } from '../src/lib/projects/server.ts';
import { createInput, projectETag } from '../src/lib/projects/contracts.ts';
import { readAttempt, ATTEMPT_STORAGE, outcomeIsUnknown, creationTarget } from '../src/lib/projects/creation.ts';
const token = 'synthetic-m3-private-token-1234567890123456789';
const env = { APP_ENV: 'test', DEV_API_TOKEN: token, API_INTERNAL_URL: 'http://127.0.0.1:8000', NEXT_PUBLIC_APP_URL: 'http://127.0.0.1:3000' };
const id = 'ab56889d-a04c-41bb-831e-429948d34cb8', key = '30fe5cca-25e1-4f68-b80a-6b281d7b5c22';
function request(method, body, headers = {}, query = '') { return new Request(`http://127.0.0.1:3000/api/v1/projects${query}`, { method, headers: { Origin: 'http://127.0.0.1:3000', 'Content-Type': 'application/json', ...headers }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) }); }
test('generated client gateway forwards trimmed creation, stable key and private identity only', async () => {
  const response = await handleProjectsRequest(request('POST', { title: ' Test ', brief: ' A CRM for estate agents and leads. ' }, { 'Idempotency-Key': key, Authorization: 'Bearer foreign', 'X-User-ID': 'foreign' }), 'projects', undefined, env, async (req, init) => {
    assert.equal(req.url, 'http://127.0.0.1:8000/v1/projects'); assert.equal(req.headers.get('Authorization'), `Bearer ${token}`); assert.equal(req.headers.get('Idempotency-Key'), key); assert.equal(req.headers.get('X-User-ID'), null); assert.deepEqual(await req.json(), { title: 'Test', brief: 'A CRM for estate agents and leads.' }); assert.equal(init.cache, 'no-store'); assert.equal(init.redirect, 'error');
    return Response.json({ project: { id }, execution_mode: 'simulated' }, { status: 201, headers: { 'Set-Cookie': 'private=secret' } });
  });
  assert.equal(response.status, 201); assert.equal(response.headers.get('Set-Cookie'), null); assert.equal(response.headers.get('Cache-Control'), 'no-store');
});
test('creation accepts the real saved-project contract and rejects unsafe navigation',()=>{
 const result={project:{id},project_url:`/projects/${id}`,request_id:key,brain_revision_id:key,execution_mode:'real',run_id:null};
 assert.equal(creationTarget(result),`/projects/${id}`);assert.equal(creationTarget({...result,execution_mode:'simulated',run_id:key}),`/projects/${id}`);assert.equal(creationTarget({...result,execution_mode:'invented'}),null);assert.equal(creationTarget({...result,project_url:'https://foreign.example'}),null);assert.equal(creationTarget({...result,run_id:'bad'}),null);assert.equal(outcomeIsUnknown(409,'IDEMPOTENCY_IN_PROGRESS'),true);assert.equal(outcomeIsUnknown(408,'timeout'),true);
});
test('list forwards validated search, lifecycle, archive and pagination', async () => {
  const response = await handleProjectsRequest(request('GET', undefined, {}, '?q=estate&status=understanding&archived=true&cursor=abc'), 'projects', undefined, env, async req => { const url = new URL(req.url); assert.equal(url.searchParams.get('q'), 'estate'); assert.equal(url.searchParams.get('status'), 'understanding'); assert.equal(url.searchParams.get('archived'), 'true'); assert.equal(url.searchParams.get('cursor'), 'abc'); assert.equal(url.searchParams.get('limit'), '20'); return Response.json({ items: [], next_cursor: null }); });
  assert.equal(response.status, 200);
});
test('metadata gateway preserves If-Match and ETag without exposing private headers', async () => {
  const etag = projectETag({ id, metadata_version: 2 });
  const response = await handleProjectsRequest(request('PATCH', { archived: true }, { 'If-Match': etag }), 'projects', id, env, async req => { assert.equal(req.headers.get('If-Match'), etag); assert.deepEqual(await req.json(), { archived: true }); return Response.json({ id }, { headers: { ETag: etag, Authorization: token } }); });
  assert.equal(response.headers.get('ETag'), etag); assert.equal(response.headers.get('Authorization'), null);
});
test('write gateway rejects cross-site, unknown fields, invalid keys and invalid metadata without backend access', async () => {
  const send = () => { throw new Error('Must not call backend'); };
  for (const [req, projectId, status] of [
    [request('POST', { brief: 'A CRM for estate agents.' }, { Origin: 'https://evil.example', 'Idempotency-Key': key }), undefined, 403],
    [request('POST', { brief: 'A CRM for estate agents.', owner_user_id: id }, { 'Idempotency-Key': key }), undefined, 422],
    [request('POST', { brief: 'A CRM for estate agents.' }), undefined, 422],
    [request('PATCH', { title: '' }, { 'If-Match': 'bad' }), id, 422],
    [request('PATCH', { archived: false }), id, 428],
    [request('PATCH', { archived: 'false' }, { 'If-Match': 'bad' }), id, 422],
    [request('GET'), 'foreign-path', 404],
    [request('GET', undefined, {}, '?status=fake'), undefined, 422],
  ]) assert.equal((await handleProjectsRequest(req, 'projects', projectId, env, send)).status, status);
});
test('gateway sanitizes domain conflicts, unknown failures and transport uncertainty', async () => {
  for (const code of ['ACTIVE_RUN_EXISTS', 'METADATA_CONFLICT', 'IDEMPOTENCY_IN_PROGRESS', 'unknown']) {
    const response = await handleProjectsRequest(request('GET'), 'projects', id, env, async () => Response.json({ error: { code, message: token + ' raw SQL' } }, { status: code === 'METADATA_CONFLICT' ? 412 : 409 }));
    const body = await response.json(); assert.equal(body.error.code, code === 'unknown' ? 'INTERNAL_ERROR' : code); assert.ok(!JSON.stringify(body).includes(token));
  }
  assert.equal((await handleProjectsRequest(request('GET'), 'projects', id, env, async () => { throw new Error('offline'); })).status, 503);
  assert.equal((await handleProjectsRequest(request('GET'), 'projects', id, env, async () => Response.json({ title: token }))).status, 502);
});
test('creation validation and unresolved-command receipt respect the recovery window boundary', () => {
  assert.deepEqual(createInput(' ', '   A CRM for estate agents.   '), { title: null, brief: 'A CRM for estate agents.' }); assert.equal(createInput('x'.repeat(101), 'A CRM for estate agents.'), null); assert.equal(createInput('', 'short'), null);
  const attempt = { key, input: createInput('CRM', 'A CRM for estate agents.'), started: Date.now() };
  assert.deepEqual(readAttempt({ getItem: name => { assert.equal(name, ATTEMPT_STORAGE); return JSON.stringify(attempt); } }), attempt); assert.equal(readAttempt({ getItem: () => 'bad' }), null); assert.equal(readAttempt({ getItem: () => { throw new Error('blocked'); } }), null);
  assert.equal(outcomeIsUnknown(503, 'SERVICE_UNAVAILABLE'), true); assert.equal(outcomeIsUnknown(0, 'offline'), true); assert.equal(outcomeIsUnknown(409, 'IDEMPOTENCY_IN_PROGRESS'), true); assert.equal(outcomeIsUnknown(422, 'VALIDATION_ERROR'), false);
});

test('creation gateway preserves the account assertion and rejects malformed binding',async()=>{
 const body={brief:'A CRM for estate agents and leads.'};
 const response=await handleProjectsRequest(request('POST',body,{'Idempotency-Key':key,'X-F01-Expected-Owner':id}),'projects',undefined,env,async req=>{assert.equal(req.headers.get('X-F01-Expected-Owner'),id);return Response.json({error:{code:'CREATION_ACCOUNT_CHANGED'}},{status:409});});
 assert.equal(response.status,409);assert.equal((await response.json()).error.code,'CREATION_ACCOUNT_CHANGED');
 assert.equal((await handleProjectsRequest(request('POST',body,{'Idempotency-Key':key,'X-F01-Expected-Owner':'bad'}),'projects',undefined,env,()=>{throw Error('No dispatch');})).status,422);
 const receipt={key,input:createInput('CRM',body.brief),started:Date.now(),owner:id};
 assert.deepEqual(readAttempt({getItem:()=>JSON.stringify(receipt)}),receipt);
 assert.equal(readAttempt({getItem:()=>JSON.stringify({...receipt,owner:'bad'})}),null);
});

test('browser harness teardown completes when a child ignores graceful shutdown',async()=>{
 const {spawn}=await import('node:child_process'),{stopBrowserServer}=await import('./browser-process.mjs');
 const child=spawn(process.execPath,['-e',"process.on('SIGTERM',()=>{});process.stdout.write('ready');setInterval(()=>{},1000)"],{stdio:['ignore','pipe','ignore']});
 await new Promise(resolve=>child.stdout.once('data',resolve));
 await stopBrowserServer(child,100);assert.equal(child.signalCode,'SIGKILL');
 await stopBrowserServer(child,100);
});
