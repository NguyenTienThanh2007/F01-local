import {stopBrowserServer,launchTestBrowser} from './browser-process.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdir, readFile } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';
const webRoot = fileURLToPath(new URL('../', import.meta.url)), root = fileURLToPath(new URL('../../../', import.meta.url));
const api = process.env.M4_API_URL, database = process.env.M4_TEST_DATABASE_URL, token = process.env.M4_TEST_TOKEN;
async function until(check) { for (let n = 0; n < 200; n++) { if (await check().catch(() => false)) return; await delay(100); } throw new Error('Expected browser state not reached'); }
async function direct(path, options = {}) { return fetch(`${api}/v1${path}`, { ...options, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...options.headers } }); }
function setup(action, created) { const result = spawnSync(`${root}/apps/api/.venv/bin/python`, ['-m', 'tests.browser_fixture', database, action], { cwd: `${root}/apps/api`, input: JSON.stringify(created), encoding: 'utf8' }); assert.equal(result.status, 0, result.stderr); return result.stdout.trim() ? JSON.parse(result.stdout) : null; }
test('M4 persisted workspace, immutable Brain, changes and isolated preview foundation', { timeout: 240000 }, async t => {
 assert.ok(api && database?.includes('/f01_test_') && token, 'Use scripts/test-m4.py with a disposable PostgreSQL database.');
 const probe = createServer(); await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve)); const port = probe.address().port; await new Promise(resolve => probe.close(resolve)); const base = `http://127.0.0.1:${port}`;
 const env = { ...process.env, APP_ENV: 'test', AUTH_MODE: 'development', EXECUTION_MODE: 'simulated', DEV_API_TOKEN: token, API_INTERNAL_URL: api, NEXT_PUBLIC_APP_URL: base }; delete env.OPENAI_API_KEY;
 const server = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', String(port)], { cwd: webRoot, env, stdio: 'ignore' }); let browser;
 async function scenario(name, fn) { let failure; await t.test(name, async () => { try { await fn(); } catch(e) { failure = e; throw e; } }); if (failure) throw failure; }
 try {
  await until(async () => (await fetch(base)).ok); browser = await launchTestBrowser({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  await mkdir(`${webRoot}/test-results/m4`, { recursive: true });
  const original = 'Build a CRM for property leads. Preserve this <script>window.stolen=true</script> as plain text.';
  const created = await (await direct('/projects', { method: 'POST', headers: { 'Idempotency-Key': 'm4-create' }, body: JSON.stringify({ title: 'Harbor M4', brief: original }) })).json(); const id = created.project.id;
  const initial = (await (await direct(`/projects/${id}/brain`)).json()).revision;
  await scenario('persisted preview-first navigation and queued state', async () => {
   await page.goto(`${base}/projects/${id}`); await page.getByRole('heading', { name: 'Harbor M4', exact: true }).waitFor(); await page.getByRole('heading', { name: 'Preview pending.', exact: true }).waitFor();
   assert.equal(await page.locator('iframe').count(), 0); assert.match(await page.getByRole('main').innerText(), /Queued · not started/);
   await page.getByRole('button', { name: 'Requests', exact: true }).first().click(); assert.equal(await page.getByRole('button', { name: 'Record change request', exact: true }).isDisabled(), true);
   await page.getByRole('textbox', { name: 'Change request' }).fill('Add a visible priority filter for property leads.');
   await page.getByRole('navigation', { name: 'Project navigation' }).getByRole('link', { name: 'Brain', exact: true }).click(); await page.getByRole('heading', { name: 'Project Brain', exact: true }).waitFor();
   assert.equal(await page.getByRole('textbox', { name: 'Change request' }).inputValue(), 'Add a visible priority filter for property leads.');
   await page.getByRole('button', { name: 'Close inspector' }).click();
   await page.reload(); await page.getByRole('heading', { name: 'Harbor M4', exact: true }).waitFor(); assert.equal((await (await direct('/projects')).json()).items.length, 1);
  });
  await scenario('structured Brain, provenance and original brief render as plain text', async () => {
   await page.getByRole('heading', { name: 'Requirements', exact: true }).waitFor();
   for (const heading of ['Ordered plan', 'Architecture · proposed', 'Intended product stack', 'Database proposal', 'Features', 'Design decisions', 'Constraints and open questions', 'Revision history references']) assert.equal(await page.getByRole('heading', { name: heading, exact: true }).count(), 1);
   assert.ok(await page.getByText('User requested', { exact: true }).count()); assert.ok(await page.getByText('Template assumption', { exact: true }).count()); assert.equal(await page.evaluate(() => window.stolen), undefined);
   await page.getByRole('navigation', { name: 'Project navigation' }).getByRole('link', { name: 'Brief', exact: true }).click(); await page.getByRole('heading', { name: 'Original brief', exact: true }).waitFor(); await page.getByText(original, { exact: true }).first().waitFor(); assert.match(await page.getByRole('main').innerText(), /<script>window.stolen=true<\/script>/);
  });
  await scenario('real request saving recovers a lost response with the same frozen command', async () => {
   setup('finish', created); await page.locator('.workspace-context-details > summary').click(); await page.getByRole('button', { name: 'Refresh context', exact: true }).click(); await until(async () => (await page.locator('.workspace-sync').innerText()).includes('Saved sequence'));
   await page.getByRole('button', { name: 'Requests', exact: true }).first().click(); const text = page.getByRole('textbox', { name: 'Change request' }); await text.fill('Add a visible priority filter for property leads.');
   const posts = []; let release;
   await page.route('**/api/v1/projects/*/requests', async route => { if (route.request().method() !== 'POST') return route.continue(); posts.push({ key: route.request().headers()['idempotency-key'], body: route.request().postDataJSON() }); const response = await route.fetch(); assert.equal(response.status(), 201); await new Promise(resolve => { release = resolve; }); await route.abort('failed'); });
   await page.getByRole('button', { name: 'Record change request', exact: true }).click(); await until(async () => Boolean(release)); assert.equal(posts.length, 1); assert.equal(await page.getByRole('button', { name: 'Recording request…' }).isDisabled(), true); release();
   await page.getByRole('button', { name: 'Retry saved request' }).waitFor(); await page.unroute('**/api/v1/projects/*/requests'); await page.reload(); await page.getByRole('button', { name: 'Requests', exact: true }).first().click(); await page.getByRole('button', { name: 'Retry saved request' }).waitFor(); assert.equal(await text.inputValue(), posts[0].body.text);
   page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/requests')) posts.push({ key: req.headers()['idempotency-key'], body: req.postDataJSON() }); });
   await page.getByRole('button', { name: 'Retry saved request' }).click(); await until(async () => (await page.getByRole('status').allTextContents()).join(' ').includes('Change request recorded.'));
   assert.equal(posts.length, 2); assert.equal(posts[0].key, posts[1].key); assert.deepEqual(posts[0].body, posts[1].body);
   assert.equal((await (await direct(`/projects/${id}/requests`)).json()).items.length, 2); assert.deepEqual((await (await direct(`/projects/${id}/brain`)).json()).revision, initial); await page.getByRole('button', { name: 'Close inspector' }).click();
  });
  await scenario('stale Brain conflict preserves text and requires current context review', async () => {
   await page.getByRole('button', { name: 'Requests', exact: true }).first().click(); const text = page.getByRole('textbox', { name: 'Change request' }); await text.fill('Add a saved view for recently contacted leads.'); setup('brain', created);
   await page.getByRole('button', { name: 'Record change request', exact: true }).click(); await page.getByRole('button', { name: 'Review current context' }).waitFor(); assert.equal(await text.inputValue(), 'Add a saved view for recently contacted leads.'); assert.equal(await page.getByRole('button', { name: 'Record change request', exact: true }).isDisabled(), true);
   await page.getByRole('button', { name: 'Review current context' }).click(); await until(async () => !(await page.getByRole('button', { name: 'Record change request', exact: true }).isDisabled())); assert.equal(await text.inputValue(), 'Add a saved view for recently contacted leads.');
   await page.getByRole('button', { name: 'Record change request', exact: true }).click(); await until(async () => (await (await direct(`/projects/${id}/requests`)).json()).items.length === 3);
   await page.getByRole('button', { name: 'Close inspector' }).click(); await page.goto(`${base}/projects/${id}/brain?revision=1`); await page.getByText('Immutable revision 1', { exact: true }).waitFor(); assert.match(await page.getByRole('main').innerText(), /HISTORICAL INSPECTION/); assert.equal((await (await direct(`/projects/${id}`)).json()).current_brain_revision_id, (await (await direct(`/projects/${id}/brain`)).json()).revision.id);
   await page.goto(`${base}/projects/${id}/activity`); await page.getByRole('heading', { name: 'Activity', exact: true }).waitFor(); await page.getByText('Change request recorded; no execution started.', { exact: true }).first().waitFor();
   await page.goto(`${base}/projects/${id}/versions`); await page.getByRole('heading', { name: 'No completed versions.', exact: true }).waitFor();
  });
  await scenario('available fixture version inspection and stale nullable base version', async () => {
   const versioned = await (await direct('/projects', { method: 'POST', headers: { 'Idempotency-Key': 'm4-versioned' }, body: JSON.stringify({ title: 'Version fixture', brief: 'Build a small CRM with property leads and saved notes.' }) })).json(); const published = setup('output', versioned); const vid = versioned.project.id;
   await page.goto(`${base}/projects/${vid}/versions`); await page.getByRole('link', { name: 'Inspect demo preview' }).click(); await page.getByRole('heading', { name: 'Demo version 1', exact: true }).waitFor(); assert.equal(await page.locator('iframe').getAttribute('sandbox'), 'allow-scripts');
   const stale = await direct(`/projects/${vid}/requests`, { method: 'POST', headers: { 'Idempotency-Key': 'stale-version' }, body: JSON.stringify({ text: 'Add a property category filter for leads.', base_brain_revision_id: published.brain, base_version_id: null }) }); assert.equal(stale.status, 409); assert.equal((await stale.json()).error.code, 'STALE_BASE_VERSION');
   await page.getByRole('button', { name: 'Requests', exact: true }).first().click(); const versionDraft = page.getByRole('textbox', { name: 'Change request' }); await versionDraft.fill('Add a property category filter for leads.'); setup('version', versioned);
   await page.getByRole('button', { name: 'Record change request', exact: true }).click(); await page.getByRole('button', { name: 'Review current context' }).waitFor(); assert.equal(await versionDraft.inputValue(), 'Add a property category filter for leads.'); assert.match((await page.getByRole('alert').allTextContents()).join(' '), /current version changed/);
   await page.getByRole('button', { name: 'Review current context' }).click(); await until(async () => !(await page.getByRole('button', { name: 'Record change request', exact: true }).isDisabled())); await page.getByRole('button', { name: 'Close inspector' }).click();
   await page.goto(`${base}/projects/${vid}?version=${published.version}`); await page.getByRole('heading', { name: 'Demo version 1', exact: true }).waitFor(); await page.getByText(/Historical demo version · inspection only/).waitFor();
   const before = await (await direct(`/projects/${vid}`)).json(); await page.goto(`${base}/projects/${vid}/brain?revision=1`); await page.getByText('Immutable revision 1', { exact: true }).waitFor(); assert.equal((await (await direct(`/projects/${vid}`)).json()).current_version_id, before.current_version_id);
  });
  await scenario('preview assets load and interactions work under opaque-origin isolation', async () => {
   await page.goto(`${base}/development/previews`); const frame = page.frameLocator('iframe'); await frame.getByRole('heading', { name: 'Good relationships, one step closer.' }).waitFor(); await frame.getByRole('searchbox', { name: 'Search sample leads' }).fill('Avery'); await frame.getByRole('status').getByText('1 sample records', { exact: true }).waitFor();
   const child = page.frames().find(f => f.url().includes('/demo-preview/crm-v1')); assert.ok(child);
   const response = await fetch(`${base}/demo-preview/crm-v1`); const csp = response.headers.get('content-security-policy'); assert.match(csp, /connect-src 'none'/); assert.match(csp, /form-action 'none'/); assert.match(csp, /frame-ancestors 'self'/); assert.match(csp, /sandbox allow-scripts/); assert.doesNotMatch(await response.text(), /NEXT_DATA|api\/v1/);
   let apiCalls = 0; page.on('request', req => { if (req.url().includes('/api/v1/session') || req.url().includes('/api/v1/projects')) apiCalls++; }); const url = page.url();
   const blocked = await child.evaluate(async () => { const blocked = {}; for (const [name, fn] of [['parent', () => parent.document], ['storage', () => localStorage.getItem('x')], ['cookies', () => document.cookie], ['top', () => { top.location.href = '/projects'; }]]) { try { fn(); blocked[name] = false; } catch { blocked[name] = true; } } try { await fetch('/api/v1/session'); blocked.fetch = false; } catch { blocked.fetch = true; } blocked.popup = window.open('/projects') === null; return blocked; });
   const formBlocked = await child.evaluate(async () => { const form = document.createElement('form'); form.action = '/api/v1/session'; form.method = 'post'; document.body.append(form); form.submit(); await new Promise(resolve => setTimeout(resolve, 30)); return location.pathname.startsWith('/demo-preview/'); }); assert.equal(formBlocked, true);
   assert.deepEqual(blocked, { parent: true, storage: true, cookies: true, top: true, fetch: true, popup: true }); assert.equal(page.url(), url); assert.equal(apiCalls, 0);
   await page.screenshot({ path: `${webRoot}/test-results/m4/showcase-1440.png`, fullPage: true });
   const rejected = await fetch(`${base}/demo-preview/unknown`); assert.equal(rejected.status, 404); await page.getByRole('combobox', { name: 'Sample fixture' }).selectOption('generic-v1'); await page.frameLocator('iframe').getByRole('heading', { name: 'A place for the next good idea.' }).waitFor();
  });
  await scenario('responsive surfaces, mobile drawer focus and stable draft state', async () => {
   for (const width of [375, 768, 1280, 1440]) for (const [path, name] of [['', 'preview'], ['/brief', 'brief'], ['/brain', 'brain'], ['/activity', 'activity'], ['/versions', 'versions'], ['/settings', 'settings']]) {
    await page.setViewportSize({ width, height: 1000 }); await page.goto(`${base}/projects/${id}${path}`); await page.getByRole('heading', { name: 'Harbor M4', exact: true }).waitFor(); await page.evaluate(() => document.fonts.ready); await until(async () => !(await page.getByRole('main').innerText()).includes('Loading saved records…'));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name} ${width}px`);
    if (process.env.M4_AXE_SCRIPT) { await page.addScriptTag({ content: await readFile(process.env.M4_AXE_SCRIPT, 'utf8') }); const violations = await page.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] } })).violations.map(v => ({ id: v.id, targets: v.nodes.map(n => n.target) }))); assert.deepEqual(violations, [], `${name} ${width}px`); }
    await page.screenshot({ path: `${webRoot}/test-results/m4/${name}-${width}.png`, fullPage: true });
   }
   await page.setViewportSize({ width: 375, height: 900 }); await page.goto(`${base}/projects/${id}`); await page.getByRole('button', { name: 'Requests', exact: true }).first().click(); const drawer = page.getByRole('dialog', { name: 'Requests', exact: true }); await drawer.waitFor(); await drawer.getByRole('textbox', { name: 'Change request' }).fill('Preserve this draft while the layout changes.'); await page.screenshot({ path: `${webRoot}/test-results/m4/requests-375.png`, fullPage: true }); await page.keyboard.press('Tab'); assert.equal(await page.evaluate(() => document.querySelector('dialog[open]').contains(document.activeElement)), true);
   await page.setViewportSize({ width: 1440, height: 1000 }); await until(async () => (await page.getByRole('textbox', { name: 'Change request' }).inputValue()) === 'Preserve this draft while the layout changes.'); await page.keyboard.press('Escape'); assert.equal(await page.getByRole('button', { name: 'Requests', exact: true }).first().evaluate(el => document.activeElement === el), true);
  });
  await scenario('missing projects, unsupported Brain schema and unavailable-service retry are safe', async () => {
   await page.goto(`${base}/projects/00000000-0000-0000-0000-000000000000`); await page.getByRole('heading', { name: 'This project is unavailable.' }).waitFor();
   const unknown = await (await direct('/projects', { method: 'POST', headers: { 'Idempotency-Key': 'unknown-schema' }, body: JSON.stringify({ title: 'Unknown schema', brief: 'A safe test fixture for an unsupported Brain schema.' }) })).json(); setup('unknown-schema', unknown); await page.goto(`${base}/projects/${unknown.project.id}/brain`); await page.getByText('This Brain schema is not supported. The saved content has not been changed.', { exact: true }).waitFor();
   await page.route('**/api/v1/projects/*/workspace', route => route.abort('failed')); await page.goto(`${base}/projects/${id}`); await page.getByRole('button', { name: 'Retry workspace' }).waitFor(); await page.unroute('**/api/v1/projects/*/workspace'); await page.getByRole('button', { name: 'Retry workspace' }).click(); await page.getByRole('heading', { name: 'Harbor M4', exact: true }).waitFor();
  });
 } finally { await browser?.close(); await stopBrowserServer(server); }
});
