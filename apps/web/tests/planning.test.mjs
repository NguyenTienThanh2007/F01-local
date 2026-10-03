import test from 'node:test';
import assert from 'node:assert/strict';
import { isProjectPlan, parseIdea, planningErrors } from '../src/lib/planning/contracts.ts';
import { handlePlanRequest } from '../src/lib/planning/server.ts';
import { projectPlan } from './fixtures/project-plan.mjs';

const token = 'synthetic-development-test-token-123456789';
const env = { APP_ENV: 'test', DEV_API_TOKEN: token, API_INTERNAL_URL: 'http://127.0.0.1:8000', NEXT_PUBLIC_APP_URL: 'http://127.0.0.1:3000' };
function request(body = { idea: '  A CRM for real estate agents.  ' }, headers = {}) {
  return new Request('http://127.0.0.1:3000/api/v1/plan', {
    method: 'POST', headers: { Origin: 'http://127.0.0.1:3000', 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body),
  });
}
async function expectError(response, code) {
  assert.equal(response.status, planningErrors[code].status);
  const payload = await response.json();
  assert.equal(payload.error.code, code);
  assert.equal(payload.error.message, planningErrors[code].message);
  assert.match(payload.error.request_id, /^[0-9a-f-]{36}$/i);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
  assert.ok(!JSON.stringify(payload).includes(token));
}

test('the proxy forwards only the trimmed idea and server credential to the fixed endpoint', async () => {
  let calls = 0;
  const response = await handlePlanRequest(request(undefined, { Authorization: 'Bearer caller-controlled', 'X-User-ID': 'foreign-user' }), env, async (url, options) => {
    calls++;
    assert.equal(url, 'http://127.0.0.1:8000/v1/plan');
    assert.equal(options.headers.Authorization, `Bearer ${token}`);
    assert.deepEqual(JSON.parse(options.body), { idea: 'A CRM for real estate agents.' });
    assert.equal(options.headers['X-User-ID'], undefined);
    assert.equal(options.redirect, 'error');
    assert.equal(options.cache, 'no-store');
    assert.ok(options.signal instanceof AbortSignal);
    return Response.json(projectPlan, { headers: { 'Set-Cookie': 'internal=value', 'X-Internal-Token': token } });
  });
  assert.equal(calls, 1);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), projectPlan);
  assert.equal(response.headers.get('Set-Cookie'), null);
  assert.equal(response.headers.get('X-Internal-Token'), null);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
});

test('rejects cross-origin, missing-origin, and forged-host requests without calling the backend', async () => {
  const send = () => assert.fail('Unexpected upstream call');
  for (const origin of ['https://attacker.invalid', '', 'null']) await expectError(await handlePlanRequest(request(undefined, { Origin: origin }), env, send), 'REQUEST_FORBIDDEN');
  await expectError(await handlePlanRequest(request(undefined, { 'Sec-Fetch-Site': 'cross-site' }), env, send), 'REQUEST_FORBIDDEN');
  await expectError(await handlePlanRequest(new Request('http://attacker.invalid:3000/api/v1/plan', { method: 'POST', headers: { Origin: 'http://attacker.invalid:3000', 'Content-Type': 'application/json' }, body: '{"idea":"CRM"}' }), env, send), 'REQUEST_FORBIDDEN');
});

test('allows localhost on the configured loopback port', async () => {
  const req = new Request('http://localhost:3000/api/v1/plan', { method: 'POST', headers: { Origin: 'http://localhost:3000', 'Content-Type': 'application/json' }, body: '{"idea":"CRM"}' });
  assert.equal((await handlePlanRequest(req, env, async () => Response.json(projectPlan))).status, 200);
});

test('binds the origin to the HTTP Host when Next normalizes the internal URL', async () => {
  const req = new Request('http://localhost:3000/api/v1/plan', { method: 'POST', headers: { Host: '127.0.0.1:3000', Origin: 'http://127.0.0.1:3000', 'Content-Type': 'application/json' }, body: '{"idea":"CRM"}' });
  assert.equal((await handlePlanRequest(req, env, async () => Response.json(projectPlan))).status, 200);
  for (const host of ['attacker.invalid:3000', '127.0.0.1:3001', '127.0.0.1:3000/path', 'user@127.0.0.1:3000']) {
    await expectError(await handlePlanRequest(request(undefined, { Host: host }), env, () => assert.fail('Unexpected upstream call')), 'REQUEST_FORBIDDEN');
  }
});

test('invalid configuration fails safely before a backend call', async () => {
  for (const invalid of [
    { DEV_API_TOKEN: '' }, { DEV_API_TOKEN: 'short' }, { DEV_API_TOKEN: token + '\n' },
    { API_INTERNAL_URL: 'http://remote.invalid' }, { API_INTERNAL_URL: 'https://user:password@example.invalid' },
    { API_INTERNAL_URL: 'http://127.0.0.1:8000/path' }, { API_INTERNAL_URL: 'http://127.0.0.1:8000?token=secret' },
    { APP_ENV: 'production' }, { NEXT_PUBLIC_APP_URL: 'https://public.invalid' },
  ]) await expectError(await handlePlanRequest(request(), { ...env, ...invalid }, () => assert.fail('Unexpected upstream call')), 'PLANNING_NOT_CONFIGURED');
});

test('validates content type, bounded bodies, JSON and strict idea input before network access', async () => {
  const send = () => assert.fail('Unexpected upstream call');
  await expectError(await handlePlanRequest(request(undefined, { 'Content-Type': 'text/plain' }), env, send), 'UNSUPPORTED_MEDIA_TYPE');
  await expectError(await handlePlanRequest(request(undefined, { 'Content-Length': String(200_000) }), env, send), 'REQUEST_TOO_LARGE');
  await expectError(await handlePlanRequest(request({ idea: 'x'.repeat(140_000) }), env, send), 'REQUEST_TOO_LARGE');
  for (const body of [{ idea: '' }, { idea: ' \n ' }, { idea: 12 }, { idea: 'a'.repeat(10_001) }, { idea: 'CRM', token }, null, [], { prompt: 'CRM' }]) {
    await expectError(await handlePlanRequest(request(body), env, send), 'VALIDATION_ERROR');
  }
  const malformed = new Request('http://127.0.0.1:3000/api/v1/plan', { method: 'POST', headers: { Origin: 'http://127.0.0.1:3000', 'Content-Type': 'application/json' }, body: '{' });
  await expectError(await handlePlanRequest(malformed, env, send), 'VALIDATION_ERROR');
  assert.equal(parseIdea({ idea: '🧱'.repeat(10_000) })?.length, 20_000);
});

for (const code of ['AUTHENTICATION_REQUIRED', 'PROVIDER_NOT_CONFIGURED', 'PROVIDER_AUTHENTICATION_FAILED', 'PROVIDER_QUOTA_EXCEEDED', 'PROVIDER_RATE_LIMITED', 'PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE', 'PROVIDER_REFUSED', 'PROVIDER_INCOMPLETE_RESPONSE', 'PROVIDER_ERROR', 'INTERNAL_ERROR', 'VALIDATION_ERROR']) {
  test(`sanitizes ${code} without relaying upstream messages`, async () => {
    const requestId = '00000000-0000-4000-8000-000000000001';
    const response = await handlePlanRequest(request(), env, async () => Response.json({ error: { code, message: 'untrusted diagnostic text', request_id: requestId, details: { secret: 'sensitive-details' } } }, { status: 503 }));
    const body = response.clone();
    await expectError(response, code);
    const payload = await body.json();
    assert.equal(payload.error.request_id, requestId);
    assert.ok(!JSON.stringify(payload).includes('untrusted diagnostic text'));
    assert.equal(payload.error.details, undefined);
  });
}

test('unknown upstream failures and thrown exceptions use static messages', async () => {
  await expectError(await handlePlanRequest(request(), env, async () => Response.json({ error: { code: 'UNSAFE', message: token } }, { status: 500 })), 'PROVIDER_INVALID_RESPONSE');
  await expectError(await handlePlanRequest(request(), env, async () => Response.json({ error: { code: 'UNKNOWN', message: 'private' } }, { status: 500 })), 'PROVIDER_ERROR');
  await expectError(await handlePlanRequest(request(), env, async () => { throw new Error(token); }), 'PROVIDER_UNAVAILABLE');
});

test('invalid, oversized and credential-bearing successful responses cannot reach the browser', async () => {
  const invalidPlans = [
    { ...projectPlan, token }, { ...projectPlan, project_title: token },
    { ...projectPlan, target_users: [] }, { ...projectPlan, core_features: [{ name: 'Lead' }] },
    { ...projectPlan, recommended_stack: { ...projectPlan.recommended_stack, extra: 'private' } },
    { ...projectPlan, implementation_milestones: [{ title: 'A', deliverables: [] }] },
    { ...projectPlan, product_summary: 'x'.repeat(1001) },
  ];
  for (const plan of invalidPlans) await expectError(await handlePlanRequest(request(), env, async () => Response.json(plan)), 'PROVIDER_INVALID_RESPONSE');
  await expectError(await handlePlanRequest(request(), env, async () => new Response('not JSON')), 'PROVIDER_INVALID_RESPONSE');
  await expectError(await handlePlanRequest(request(), env, async () => new Response('x'.repeat(300_000))), 'PROVIDER_INVALID_RESPONSE');
  assert.equal(isProjectPlan(projectPlan), true);
  assert.equal(isProjectPlan({ ...projectPlan, target_users: Array(11).fill('user') }), false);
  assert.equal(isProjectPlan({ ...projectPlan, core_features: Array(17).fill(projectPlan.core_features[0]) }), false);
  assert.equal(isProjectPlan({ ...projectPlan, implementation_milestones: Array(13).fill(projectPlan.implementation_milestones[0]) }), false);
});

test('browser cancellation reaches the upstream signal with no retry', async () => {
  const controller = new AbortController();
  const req = new Request(request(), { signal: controller.signal });
  let calls = 0;
  await handlePlanRequest(req, env, async (_url, options) => {
    calls++;
    controller.abort();
    assert.equal(options.signal.aborted, true);
    throw new Error('Canceled');
  });
  assert.equal(calls, 1);
});
