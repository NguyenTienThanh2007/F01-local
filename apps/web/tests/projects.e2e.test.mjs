import {stopBrowserServer,launchTestBrowser} from './browser-process.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { mkdir, readFile } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';
const webRoot = fileURLToPath(new URL('../', import.meta.url));
const root = fileURLToPath(new URL('../../../', import.meta.url));
const api = process.env.M3_API_URL, database = process.env.M3_TEST_DATABASE_URL, token = process.env.M3_TEST_TOKEN;
async function until(check) { for (let n = 0; n < 150; n++) { if (await check().catch(() => false)) return; await delay(100); } throw new Error('Expected state not reached'); }
async function direct(path, options = {}) { return fetch(`${api}/v1${path}`, { ...options, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...options.headers } }); }

test('M3 real PostgreSQL project create, recover, reload, search and metadata journey', { timeout: 150000 }, async () => {
  assert.ok(api && database?.includes('/f01_test_') && token, 'Run with scripts/test-m3.py against its disposable PostgreSQL database.');
  const probe = createServer(); await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve)); const port = probe.address().port; await new Promise(resolve => probe.close(resolve)); const base = `http://127.0.0.1:${port}`;
  const env = { ...process.env, APP_ENV: 'test', AUTH_MODE: 'development', EXECUTION_MODE: 'simulated', DEV_API_TOKEN: token, API_INTERNAL_URL: api, NEXT_PUBLIC_APP_URL: base }; delete env.OPENAI_API_KEY;
  const server = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', String(port)], { cwd: webRoot, env, stdio: 'ignore' }); let browser;
  try {
    await until(async () => (await fetch(base)).ok);
    browser = await launchTestBrowser({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    await mkdir(`${webRoot}/test-results/m3`, { recursive: true });
    let releaseList;
    await page.route('**/api/v1/projects?**', async route => { await new Promise(resolve => { releaseList = resolve; }); await route.continue(); });
    await page.goto(`${base}/projects`); await page.getByText('Loading saved projects…', { exact: true }).waitFor(); await page.screenshot({ path: `${webRoot}/test-results/m3/loading.png`, fullPage: true });
    await until(async () => Boolean(releaseList)); releaseList();
    await page.getByRole('heading', { name: /Start with a brief/ }).waitFor(); await page.unroute('**/api/v1/projects?**'); await page.screenshot({ path: `${webRoot}/test-results/m3/empty.png`, fullPage: true });
    await page.getByRole('link', { name: 'New project' }).click();
    const title = page.getByRole('textbox', { name: /Project title/ }), brief = page.getByRole('textbox', { name: 'Product brief' });
    await page.getByRole('button', { name: 'Create demo project' }).click(); await page.getByRole('main').getByRole('alert').waitFor(); assert.equal((await (await direct('/projects')).json()).items.length, 0);
    await title.fill('x'.repeat(101)); await brief.fill('Build a CRM for a small real estate agency with leads, pipeline, notes and analytics.');
    await page.getByRole('button', { name: 'Create demo project' }).click(); assert.equal(await title.inputValue(), 'x'.repeat(101)); assert.equal((await (await direct('/projects')).json()).items.length, 0);
    await title.fill('Harbor CRM M3'); await brief.fill('x'.repeat(10001)); await page.getByRole('button', { name: 'Create demo project' }).click(); assert.equal((await brief.inputValue()).length, 10001); assert.equal((await (await direct('/projects')).json()).items.length, 0);
    await brief.fill('Build a CRM for a small real estate agency with leads, pipeline, notes and analytics.');
    const posts = []; let release;
    await page.route('**/api/v1/projects', async route => {
      if (route.request().method() !== 'POST') return route.continue();
      posts.push({ key: route.request().headers()['idempotency-key'], body: route.request().postDataJSON() });
      const response = await route.fetch(); assert.equal(response.status(), 201);
      await new Promise(resolve => { release = resolve; }); await route.abort('failed');
    });
    await page.getByRole('button', { name: 'Create demo project' }).click(); await until(async () => Boolean(release));
    assert.equal(await page.getByRole('button', { name: 'Saving project…' }).isDisabled(), true); assert.equal(posts.length, 1); release();
    await page.getByRole('button', { name: 'Retry project creation' }).waitFor();
    assert.equal(await title.inputValue(), 'Harbor CRM M3'); assert.match(await brief.inputValue(), /real estate/); assert.equal(await title.getAttribute('readonly'), '');
    await page.screenshot({ path: `${webRoot}/test-results/m3/uncertain-create.png`, fullPage: true });
    await page.unroute('**/api/v1/projects'); await page.reload(); await page.getByRole('button', { name: 'Retry project creation' }).waitFor();
    assert.equal(await title.inputValue(), 'Harbor CRM M3');
    page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/api/v1/projects')) posts.push({ key: req.headers()['idempotency-key'], body: req.postDataJSON() }); });
    await page.getByRole('button', { name: 'Retry project creation' }).click(); await page.waitForURL(/\/projects\/[0-9a-f-]{36}$/); await page.getByRole('heading', { name: 'Harbor CRM M3', exact: true }).waitFor();
    assert.equal(posts.length, 2); assert.equal(posts[0].key, posts[1].key); assert.deepEqual(posts[0].body, posts[1].body);
    const id = new URL(page.url()).pathname.split('/').at(-1); assert.equal((await (await direct('/projects')).json()).items.length, 1);
    await page.reload(); await page.getByRole('heading', { name: 'Harbor CRM M3', exact: true }).waitFor(); assert.equal(new URL(page.url()).pathname, `/projects/${id}`);
    await page.goto(`${base}/projects/${id}/settings`); await page.getByRole('heading', { name: 'Harbor CRM M3', exact: true }).waitFor();
    const metadata = page.getByRole('textbox', { name: 'Project title', exact: true }); await metadata.fill('Harbor Operations'); await page.getByRole('button', { name: 'Save title' }).click(); await page.getByRole('heading', { name: 'Harbor Operations', exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Archive project', exact: true }).isDisabled(), true); assert.match(await page.getByRole('main').innerText(), /queued or running/); await page.getByRole('link', { name: /Inspect or cancel the simulation/ }).waitFor(); assert.equal((await (await direct(`/projects/${id}`)).json()).archived_at, null);
    // This setup only terminates the disposable test fixture. It adds no simulator/cancel endpoint.
    const setup = spawnSync(`${root}/apps/api/.venv/bin/python`, ['-c', `import sys,psycopg\nwith psycopg.connect(sys.argv[1]) as c:\n c.execute("UPDATE build_runs SET status='canceled',finished_at=now() WHERE project_id=%s",(sys.argv[2],))\n c.execute("UPDATE projects SET lifecycle='idle' WHERE id=%s",(sys.argv[2],))`, database.replace('postgresql+psycopg:', 'postgresql:'), id], { encoding: 'utf8' }); assert.equal(setup.status, 0, setup.stderr);
    await page.locator('.workspace-context-details > summary').click(); await page.getByRole('button', { name: 'Refresh context' }).click(); await until(async () => !(await page.getByRole('button', { name: 'Archive project', exact: true }).isDisabled()));
    await page.getByRole('button', { name: 'Archive project', exact: true }).click(); await page.getByRole('button', { name: 'Unarchive project' }).waitFor(); await page.reload(); await page.getByRole('button', { name: 'Unarchive project' }).waitFor();
    assert.ok((await (await direct(`/projects/${id}`)).json()).archived_at);
    await page.goto(`${base}/projects`); await page.getByRole('heading', { name: /Start with a brief/ }).waitFor();
    await page.locator('.dashboard-filters > summary').click(); await page.getByRole('combobox', { name: 'Archive filter' }).selectOption('true'); await page.getByRole('button', { name: 'Apply filters' }).click(); await page.getByRole('link', { name: /Harbor Operations/ }).waitFor();
    await page.getByRole('button', { name: 'Project settings', exact: true }).click(); await page.getByRole('button', { name: 'Unarchive project' }).click(); await page.getByRole('heading', { name: 'No projects in this view.' }).waitFor();
    await page.goto(`${base}/projects`); await page.getByRole('link', { name: /Harbor Operations/ }).waitFor();
    await page.locator('.dashboard-filters > summary').click(); await page.getByRole('searchbox', { name: 'Search projects' }).fill('Harbor'); await page.getByRole('combobox', { name: 'Project state' }).selectOption('idle'); await page.getByRole('button', { name: 'Apply filters' }).click(); await page.getByRole('link', { name: /Harbor Operations/ }).waitFor();
    await page.reload(); await page.getByRole('link', { name: /Harbor Operations/ }).waitFor(); assert.equal(await page.getByRole('searchbox').inputValue(), 'Harbor');
    await page.locator('.dashboard-filters > summary').click(); await page.getByRole('searchbox').fill('no match'); await page.getByRole('button', { name: 'Apply filters' }).click(); await page.getByRole('heading', { name: 'No projects in this view.' }).waitFor();
    await page.goto(`${base}/projects/${id}/settings`); await page.getByRole('heading', { name: 'Harbor Operations', exact: true }).waitFor();
    const current = await direct(`/projects/${id}`); await direct(`/projects/${id}`, { method: 'PATCH', headers: { 'If-Match': current.headers.get('etag') }, body: JSON.stringify({ title: 'Changed in another tab' }) });
    await metadata.fill('My preserved title'); await page.getByRole('button', { name: 'Review latest metadata' }).waitFor(); assert.equal(await page.getByRole('button', { name: 'Save title' }).isDisabled(), true); assert.equal(await metadata.inputValue(), 'My preserved title');
    await page.getByRole('button', { name: 'Review latest metadata' }).click(); await until(async () => (await page.getByRole('status').allTextContents()).join(' ').includes('Changed in another tab')); await page.getByRole('button', { name: 'Save title' }).click(); await page.getByRole('heading', { name: 'My preserved title', exact: true }).waitFor();
    await page.route('**/api/v1/projects?**', async route => { await delay(600); await route.abort('failed'); }); await page.goto(`${base}/projects`); await page.getByRole('button', { name: 'Retry project list' }).waitFor(); await page.screenshot({ path: `${webRoot}/test-results/m3/unavailable.png`, fullPage: true }); await page.unroute('**/api/v1/projects?**'); await page.getByRole('button', { name: 'Retry project list' }).click(); await page.getByRole('link', { name: /My preserved title/ }).waitFor();
    const axePath = process.env.M3_AXE_SCRIPT;
    for (const [path, name] of [['/projects', 'dashboard'], ['/projects/new', 'create'], [`/projects/${id}`, 'record']]) for (const width of [375, 768, 1280, 1440]) {
      await page.setViewportSize({ width, height: 1000 }); await page.goto(`${base}${path}`); await page.evaluate(() => document.fonts.ready);
      if (name === 'dashboard') await page.getByRole('link', { name: /My preserved title/ }).waitFor(); if (name === 'record') await page.getByRole('heading', { name: 'My preserved title', exact: true }).waitFor();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name} ${width}px`);
      if (axePath) { await page.addScriptTag({ content: await readFile(axePath, 'utf8') }); const violations = await page.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } })).violations.map(x => ({ id: x.id, targets: x.nodes.map(n => n.target) }))); assert.deepEqual(violations, [], `${name} ${width}px accessibility`); }
      await page.screenshot({ path: `${webRoot}/test-results/m3/${name}-${width}.png`, fullPage: true });
    }
    assert.equal((await (await direct('/projects')).json()).items.length, 1); assert.equal((await (await direct(`/projects/${id}`)).json()).title, 'My preserved title');
  } finally { await browser?.close(); await stopBrowserServer(server); }
});
