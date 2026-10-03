import test from 'node:test';
import assert from 'node:assert/strict';
import { handleWorkspaceRequest } from '../src/lib/workspace/server.ts';
import { changeInput, readChangeAttempt, fixturePath } from '../src/lib/workspace/contracts.ts';
import { previewCSP, fixtureHTML, fixtureJS } from '../src/fixtures/previews/fixtures.ts';
const id = 'ab56889d-a04c-41bb-831e-429948d34cb8', key = '30fe5cca-25e1-4f68-b80a-6b281d7b5c22';
const token = 'synthetic-m4-token-12345678901234567890';
const env = { APP_ENV: 'test', DEV_API_TOKEN: token, API_INTERNAL_URL: 'http://127.0.0.1:8000', NEXT_PUBLIC_APP_URL: 'http://127.0.0.1:3000' };
const body = { text: ' Add a filter for high priority leads. ', base_brain_revision_id: id, base_version_id: null };
const request = (method, data, query = '', origin = 'http://127.0.0.1:3000') => new Request('http://127.0.0.1:3000/api/v1/projects/' + id + '/requests' + query, { method, headers: { Origin: origin, 'Content-Type': 'application/json', 'Idempotency-Key': key, Authorization: 'Bearer forged', 'X-User-ID': 'forged' }, ...(data ? { body: JSON.stringify(data) } : {}) });
test('change gateway preserves frozen context and idempotency, keeps identity private', async () => {
 const response = await handleWorkspaceRequest(request('POST', body), id, 'requests', env, undefined, async (req, init) => {
  assert.equal(req.url, `http://127.0.0.1:8000/v1/projects/${id}/requests`); assert.equal(req.headers.get('Authorization'), `Bearer ${token}`); assert.equal(req.headers.get('X-User-ID'), null); assert.equal(req.headers.get('Idempotency-Key'), key); assert.equal(init.redirect, 'error');
  assert.deepEqual(await req.json(), { ...body, text: body.text.trim() }); return Response.json({ id }, { status: 201, headers: { 'Set-Cookie': 'secret=1' } });
 }); assert.equal(response.status, 201); assert.equal(response.headers.get('Set-Cookie'), null); assert.equal(response.headers.get('Cache-Control'), 'no-store');
});
test('workspace gateway rejects foreign writes, invalid bases, execution fields and methods before transport', async () => {
 let calls = 0; const send = async () => { calls++; return Response.json({}); };
 for (const [req, resource, status] of [[request('POST', body, '', 'https://foreign.test'), 'requests', 403], [request('POST', { ...body, execute: true }), 'requests', 422], [request('POST', { ...body, base_version_id: 'bad' }), 'requests', 422], [request('POST', body), 'workspace', 405]]) assert.equal((await handleWorkspaceRequest(req, id, resource, env, undefined, send)).status, status);
 assert.equal(calls, 0);
});
test('typed read routes forward revision, event sequence and pagination only', async () => {
 for (const [resource, query, expected] of [['brain','?revision=2','brain?revision=2'], ['events','?after_sequence=7','events?after_sequence=7&limit=20'], ['brain/revisions','?cursor=abc','brain/revisions?cursor=abc&limit=20'], ['versions','','versions?limit=20']]) {
  const response = await handleWorkspaceRequest(request('GET', null, query), id, resource, env, undefined, async req => { assert.equal(req.url, `http://127.0.0.1:8000/v1/projects/${id}/${expected}`); return Response.json({ items: [], next_cursor: null }); }); assert.equal(response.status, 200);
 }
});
test('stale and unsupported-schema conflicts survive sanitized gateway errors', async () => {
 for (const code of ['STALE_BRAIN_REVISION','STALE_BASE_VERSION','UNSUPPORTED_BRAIN_SCHEMA']) { const response = await handleWorkspaceRequest(request('GET'), id, 'brain', env, undefined, async () => Response.json({ error: { code, message: token } }, { status: 409 })); assert.equal(response.status, 409); const value = await response.json(); assert.equal(value.error.code, code); assert.equal(JSON.stringify(value).includes(token), false); }
});
test('change receipts preserve exact command and reject invalid saved references', () => {
 assert.equal(changeInput(' ', id, null), null); assert.equal(changeInput('x'.repeat(10001), id, null), null); assert.equal(changeInput('Change', id, 'bad'), null);
 const attempt = { key, input: changeInput('Add a search filter for leads', id, null), started: Date.now() }; assert.deepEqual(readChangeAttempt({ getItem: () => JSON.stringify(attempt) }, 'key'), attempt); assert.equal(readChangeAttempt({ getItem: () => JSON.stringify({ ...attempt, key: 'bad' }) }, 'key'), null);
});
test('fixture descriptors cannot open arbitrary URLs or unknown fixture revisions', () => {
 assert.equal(fixturePath({ kind: 'fixture', fixture_id: 'crm-v1' }), '/demo-preview/crm-v1'); assert.equal(fixturePath({ kind: 'fixture', fixture_id: 'https://evil.test' }), null); assert.equal(fixturePath({ kind: 'fixture', fixture_id: 'generic-v1', fixture_revision: 2 }), null);
 assert.match(previewCSP, /connect-src 'none'/); assert.match(previewCSP, /sandbox allow-scripts/); assert.doesNotMatch(previewCSP, /allow-same-origin|unsafe-inline|unsafe-eval/); assert.doesNotMatch(fixtureHTML('crm-v1'), /NEXT_DATA|api\/v1|auth/i); assert.doesNotMatch(fixtureJS, /fetch\(|localStorage|cookie|postMessage/);
});
