import {stopBrowserServer,launchTestBrowser} from './browser-process.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';

const webRoot = fileURLToPath(new URL('../', import.meta.url));
const root = fileURLToPath(new URL('../../../', import.meta.url));
const api = process.env.M5_API_URL, token = process.env.M5_TEST_TOKEN;
async function until(check) {
  for (let i = 0; i < 300; i++) { if (await check().catch(() => false)) return; await delay(100); }
  throw new Error('Expected Phase 1 state not reached');
}
async function response(path, options = {}) {
  return fetch(`${api}/v1${path}`, { ...options, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...options.headers } });
}
async function direct(path, options = {}) {
  const value = await response(path, options); assert.equal(value.ok, true, `${path}: ${value.status}`); return value.json();
}
const saved = id => direct(`/projects/${id}/workspace`);

test('M6 final Phase 1 acceptance and product quality', { timeout: 300000 }, async t => {
  assert.ok(api && token && process.env.M5_TEST_DATABASE_URL?.includes('/f01_test_'), 'Use scripts/test-m5.py --phase1 with disposable storage.');
  const probe = createServer(); await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve));
  const port = probe.address().port; await new Promise(resolve => probe.close(resolve)); const base = `http://127.0.0.1:${port}`;
  const env = { ...process.env, APP_ENV: 'test', AUTH_MODE: 'development', DEV_API_TOKEN: token, API_INTERNAL_URL: api, NEXT_PUBLIC_APP_URL: base }; delete env.OPENAI_API_KEY;
  const server = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', String(port)], { cwd: webRoot, env, stdio: 'ignore' });
  let browser, page, id, firstVersion, finalVersion, longId;
  const errors = [], measurements = [], evidence = `${webRoot}/test-results/m6`;
  async function scenario(name, fn) {
    console.info(`Phase 1 scenario: ${name}`);let failure; await t.test(name, async () => { try { await fn(); } catch (error) { failure = error; await page?.screenshot({ path: `${evidence}/failure.png`, fullPage: true }); throw error; } });
    if (failure) throw failure;
  }
  async function scan(target, label) {
    assert.equal(await target.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${label}: page overflow`);
    await target.evaluate(() => document.fonts.ready);
    if (process.env.M5_AXE_SCRIPT) {
      await target.addScriptTag({ content: await readFile(process.env.M5_AXE_SCRIPT, 'utf8') });
      const violations = await target.evaluate(async () => (await axe.run(document, { iframes: false, runOnly: { type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] } })).violations.map(v => ({ id: v.id, targets: v.nodes.map(n => n.target) })));
      assert.deepEqual(violations, [], label);
    }
  }
  try {
    await until(async () => (await fetch(base)).ok);
    browser = await launchTestBrowser({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH });
    page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    page.setDefaultTimeout(15000);page.setDefaultNavigationTimeout(15000);
    page.on('pageerror', error => errors.push(error.message));
    await mkdir(evidence, { recursive: true });

    await scenario('one persisted journey covers lifecycle, Brain, history, cancel and metadata', async () => {
      await page.goto(`${base}/projects`); await page.getByRole('heading', { name: /Start with a brief/ }).waitFor();
      await page.getByRole('link', { name: 'New project' }).click();
      await page.locator('.creation-title-details > summary').click();
      await page.getByRole('textbox', { name: /Project title/ }).fill('Phase 1 acceptance');
      const original = 'Build a CRM with property leads, pipeline stages and private notes.';
      await page.getByRole('textbox', { name: 'Product brief' }).fill(original);
      const started = performance.now(); await page.getByRole('button', { name: 'Create demo project' }).click();
      await page.waitForURL(/\/projects\/[0-9a-f-]{36}$/); id = new URL(page.url()).pathname.split('/').at(-1);
      await page.getByRole('heading', { name: 'Phase 1 acceptance', exact: true }).waitFor();
      measurements.push({ action: 'local create to saved workspace', milliseconds: Math.round(performance.now() - started) });
      await page.reload(); await page.getByRole('heading', { name: 'Phase 1 acceptance', exact: true }).waitFor();
      await page.goto(`${base}/projects`); await page.getByRole('link', { name: /Phase 1 acceptance/ }).click();
      await page.getByRole('heading', { name: 'Demo version 1', exact: true }).waitFor();
      const initial = await saved(id); firstVersion = initial.current_version.id;
      await page.getByRole('button', { name: 'Inspect work', exact: true }).click();
      await page.getByText('Event connection: live', { exact: true }).waitFor();
      const sequences = await page.locator('.trace-scroll li[data-sequence]').evaluateAll(rows => rows.map(row => Number(row.dataset.sequence)));
      assert.equal(new Set(sequences).size, sequences.length); assert.deepEqual([...sequences].sort((a,b) => a-b), sequences);
      await page.getByText(/Event references · #/).last().click(); assert.match(await page.locator('.trace-references[open]').innerText(), /UTC timestamp/);
      await page.getByRole('button', { name: 'Close inspector' }).click();
      await page.getByRole('navigation', { name: 'Project navigation' }).getByRole('link', { name: 'Brain', exact: true }).click();
      await page.getByText('Immutable revision 2', { exact: true }).waitFor();
      await page.getByRole('navigation', { name: 'Project navigation' }).getByRole('link', { name: 'Versions', exact: true }).click();
      await page.getByText('SIMULATION / VERSION 1 · CURRENT', { exact: true }).waitFor();
      await page.getByRole('navigation', { name: 'Project navigation' }).getByRole('link', { name: 'Preview', exact: true }).click();
      await page.getByRole('button', { name: 'Requests', exact: true }).first().click();
      await page.getByRole('textbox', { name: 'Change request' }).fill('Add a priority view for the property leads in this existing project.');
      await page.getByRole('checkbox', { name: 'Run an optional demonstration after saving' }).check();
      await page.getByRole('button', { name: 'Record and simulate', exact: true }).click();
      await until(async () => (await saved(id)).latest_run.status === 'failed');
      await page.getByText(/Latest update needs attention/).waitFor();
      assert.equal((await saved(id)).current_version.id, firstVersion); assert.equal((await saved(id)).current_brain.id, initial.current_brain.id);
      await page.getByRole('button', { name: 'Run details', exact: true }).click(); await page.getByRole('button', { name: 'Retry simulation', exact: true }).click();
      await page.getByRole('heading', { name: 'Demo version 2', exact: true }).waitFor(); finalVersion = (await saved(id)).current_version.id;
      await page.getByRole('button', { name: 'Close inspector' }).click();
      await page.goto(`${base}/projects/${id}?version=${firstVersion}`);
      await page.getByText(/Historical demo version · inspection only/).waitFor();
      assert.equal((await saved(id)).current_version.id, finalVersion); assert.equal((await saved(id)).current_brain.revision, 3);
      await page.getByRole('link', { name: /Return to current preview/ }).click();
      await page.getByRole('button', { name: 'Requests', exact: true }).first().click();
      await page.getByRole('textbox', { name: 'Change request' }).fill('Demonstrate another lead filter while retaining the successful sample.');
      await page.getByRole('checkbox', { name: 'Run an optional demonstration after saving' }).check();
      await page.getByRole('button', { name: 'Record and simulate', exact: true }).click();
      await until(async () => Boolean((await saved(id)).active_run));
      await page.getByRole('button', { name: 'Run details', exact: true }).click(); await page.getByRole('button', { name: 'Cancel simulation', exact: true }).click();
      await until(async () => (await saved(id)).latest_run.status === 'canceled');
      assert.equal((await saved(id)).project.lifecycle, 'live'); assert.equal((await saved(id)).current_version.id, finalVersion);
      await page.getByRole('button', { name: 'Close inspector' }).click();
      await page.getByRole('navigation', { name: 'Project navigation' }).getByRole('link', { name: 'Settings', exact: true }).click();
      await page.getByRole('textbox', { name: 'Project title', exact: true }).fill('Phase 1 reviewed');
      let patches = 0; const count = request => { if (request.method() === 'PATCH') patches++; }; page.on('request', count);
      await page.getByRole('button', { name: 'Save title', exact: true }).evaluate(button => { button.click(); button.click(); });
      await page.getByRole('heading', { name: 'Phase 1 reviewed', exact: true }).waitFor(); page.off('request', count); assert.equal(patches, 1);
      await page.getByRole('button', { name: 'Archive project', exact: true }).click(); await page.getByRole('button', { name: 'Unarchive project', exact: true }).waitFor();
      await page.goto(`${base}/projects`); await page.getByRole('heading', { name: /Start with a brief/ }).waitFor();
      await page.locator('.dashboard-filters > summary').click(); await page.getByRole('combobox', { name: 'Archive filter' }).selectOption('true'); await page.getByRole('button', { name: 'Apply filters' }).click();
      await page.getByRole('link', { name: /Phase 1 reviewed/ }).waitFor();
      await page.getByRole('button', { name: 'Project settings', exact: true }).click(); await page.getByRole('button', { name: 'Unarchive project', exact: true }).click();
      await page.getByRole('heading', { name: 'No projects in this view.' }).waitFor(); await page.goto(`${base}/projects`); await page.getByRole('link', { name: /Phase 1 reviewed/ }).waitFor();
      const requests = (await direct(`/projects/${id}/requests`)).items; assert.equal(requests.find(r => r.kind === 'initial').text, original);
      const final = await saved(id); assert.equal(final.current_version.id, finalVersion); assert.equal(final.project.archived_at, null);
      assert.equal((await direct(`/projects/${id}/deployments`)).items.every(record => record.mode === 'simulated' && record.external_url === null), true);
    });

    await scenario('long content, all workspace surfaces and compact navigation remain accessible', async () => {
      const title = 'W'.repeat(100); const prefix = 'A generic booking workspace with a very long saved original brief.\n';
      const suffix = '\n<script>window.notExecutable=true</script>'; const brief = prefix + 'X'.repeat(10000-prefix.length-suffix.length) + suffix;
      const created = await direct('/projects', { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ title, brief }) });
      longId = created.project.id; await until(async () => (await saved(longId)).latest_run.status === 'succeeded');
      for (const width of [375,768,1280,1440]) {
        await page.setViewportSize({ width, height: 1000 });
        for (const suffix of ['', '/brief', '/brain', '/activity', '/versions', '/settings']) {
          await page.goto(`${base}/projects/${longId}${suffix}`); await page.getByRole('heading', { name: title, exact: true }).waitFor();
          if (suffix === '/brain') await page.getByText('Immutable revision 2', { exact: true }).waitFor();
          if (suffix === '/brief') { await page.locator('.preserved-text').first().waitFor(); assert.equal(await page.locator('.preserved-text').first().innerText(), brief); assert.equal(await page.evaluate(() => window.notExecutable), undefined); }
          await scan(page, `${width}px ${suffix || 'preview'} long content`);
        }
        await page.goto(`${base}/projects/${longId}?panel=trace`); await page.getByRole('heading', { name: 'Saved execution timeline', exact: true }).waitFor();
        await page.getByText('Event connection: live', { exact: true }).waitFor();
        const trace = page.getByLabel('Ordered Build Trace', { exact: true }); await until(async () => trace.evaluate(element => element.scrollHeight-element.clientHeight-element.scrollTop < 24));
        const last = await trace.locator('li[data-sequence]').last().boundingBox(); assert.ok(last && last.y+last.height <= 1000, `${width}px latest Trace event inside viewport`);
        await scan(page, `${width}px Trace`); await page.screenshot({ path: `${evidence}/trace-${width}.png`, fullPage: true });
        await page.getByRole('button', { name: 'Run details', exact: true }).click(); await scan(page, `${width}px Run details`);
        await page.getByRole('button', { name: 'Close inspector' }).click();
      }
      await page.setViewportSize({ width: 1100, height: 700 }); await page.goto(`${base}/projects/${longId}`);
      assert.equal(await page.locator('.global-rail').getByRole('link', { name: 'Projects', exact: true }).count(), 1);
      assert.equal(await page.locator('.global-rail').getByRole('link', { name: 'Start', exact: true }).count(), 1); await scan(page, 'Compact 1100px rail');
      for (const path of ['/', '/projects', '/projects/new', '/account', '/development/design-system', '/development/previews']) {
        await page.goto(`${base}${path}`); await scan(page, `Final ${path}`);
      }
      if (process.env.M5_AXE_SCRIPT) {
        const axeSource = await readFile(process.env.M5_AXE_SCRIPT,'utf8');
        for (const fixture of ['crm-v1','generic-v1']) {
          await page.getByRole('combobox',{name:'Sample fixture'}).selectOption(fixture);
          await until(async () => page.frames().some(frame => frame.url().includes(`/demo-preview/${fixture}`)));
          const frame=page.frames().find(frame => frame.url().includes(`/demo-preview/${fixture}`)); await frame.locator('h1').waitFor(); await frame.evaluate(axeSource);
          const violations=await frame.evaluate(async () => (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})));
          assert.deepEqual(violations,[],`${fixture} isolated sample accessibility`);
        }
      }
    });

    await scenario('keyboard focus, 200% reflow and reduced motion keep every control reachable', async () => {
      await page.setViewportSize({ width: 375, height: 812 }); await page.goto(`${base}/projects/${id}`);
      await page.getByRole('heading', { name: 'Phase 1 reviewed', exact: true }).waitFor();
      await page.keyboard.press('Tab'); await page.keyboard.press('Enter'); assert.equal(await page.evaluate(() => document.activeElement.id), 'main-content');
      const opener = page.getByRole('button', { name: 'Inspect work', exact: true }); await opener.focus(); await page.keyboard.press('Enter');
      const dialog = page.getByRole('dialog', { name: 'Utility inspector', exact: true }); await dialog.waitFor();
      assert.equal(await page.evaluate(() => Boolean(document.activeElement.closest('dialog[open]'))), true);
      await page.keyboard.press('Shift+Tab'); assert.equal(await page.evaluate(() => Boolean(document.activeElement.closest('dialog[open]'))), true);
      await page.keyboard.press('Escape'); await until(async () => !(await dialog.isVisible())); assert.equal(await opener.evaluate(element => element === document.activeElement), true);
      const navigation = page.getByRole('button', { name: 'Open navigation', exact: true }); await navigation.focus(); await page.keyboard.press('Enter');
      await page.getByRole('dialog', { name: 'Navigation', exact: true }).waitFor(); await page.keyboard.press('Escape');
      assert.equal(await navigation.evaluate(element => element === document.activeElement), true);
      await page.screenshot({ path: `${evidence}/keyboard-375.png`, fullPage: true });
      const zoom = await browser.newPage({ viewport: { width: 720, height: 500 }, deviceScaleFactor: 2, reducedMotion: 'reduce' });
      for (const suffix of ['', '/brain', '/versions', '/settings', '?panel=trace', '?panel=requests']) {
        await zoom.goto(`${base}/projects/${longId}${suffix}`); await zoom.getByRole('heading', { name: 'W'.repeat(100), exact: true }).waitFor();
        if (suffix.startsWith('?panel=')) await zoom.getByRole('dialog').filter({ has: zoom.getByRole('button', { name: 'Close inspector' }) }).waitFor();
        await scan(zoom, `200% equivalent reflow ${suffix}`);
        assert.equal(await zoom.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches), true);
        assert.deepEqual(await zoom.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running').map(animation => animation.animationName)), []);
      }
      await zoom.goto(`${base}/projects/${longId}`);
      const sample = zoom.locator('iframe[title="Synthetic generic preview"]'); await sample.scrollIntoViewIfNeeded();
      await sample.contentFrame().locator('h1').waitFor(); await zoom.evaluate(() => window.scrollTo(0,0));
      await zoom.getByRole('button', { name: 'Inspect work', exact: true }).click();
      await zoom.getByRole('button', { name: 'Build Trace', exact: true }).click();
      await zoom.getByRole('heading', { name: 'Saved execution timeline', exact: true }).waitFor();
      await zoom.getByText('Event connection: live', { exact: true }).waitFor();
      const zoomTrace=zoom.getByLabel('Ordered Build Trace', { exact: true }); await until(async () => zoomTrace.evaluate(element => element.scrollHeight-element.clientHeight-element.scrollTop < 24));
      const zoomLast=await zoomTrace.locator('li[data-sequence]').last().boundingBox();
      await zoom.screenshot({ path: `${evidence}/zoom-200.png`, fullPage: true });
      assert.ok(zoomLast && zoomLast.y+zoomLast.height <= 500, '200% reflow latest Trace event inside viewport'); await zoom.close();
      await page.goto(base); await page.locator('.welcome-draft > summary').click(); await page.getByRole('button', { name: 'Play demo', exact: true }).click(); await delay(150);
      assert.deepEqual(await page.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running').map(animation => animation.animationName)), []);
    });

    await scenario('offline content, explicit reconnect and historical selection recover coherently', async () => {
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.route('**/api/v1/projects/*/events?**', route => route.abort('failed'));
      await page.route('**/api/v1/projects/*/events/stream?**', route => route.abort('failed'));
      await page.goto(`${base}/projects/${id}`); await page.getByRole('heading', { name: 'Phase 1 reviewed', exact: true }).waitFor();
      await page.getByText(/Offline · saved context remains visible/).waitFor(); await page.getByRole('heading', { name: 'Demo version 2', exact: true }).waitFor();
      assert.equal((await saved(id)).project.lifecycle, 'live'); await page.screenshot({ path: `${evidence}/offline.png`, fullPage: true });
      await page.unroute('**/api/v1/projects/*/events?**'); await page.unroute('**/api/v1/projects/*/events/stream?**');
      const start = performance.now(); await page.getByRole('button', { name: 'Retry connection', exact: true }).click();
      await until(async () => !(await page.getByRole('button', { name: 'Retry connection', exact: true }).isVisible()));
      measurements.push({ action: 'explicit reconnect to saved event connection', milliseconds: Math.round(performance.now()-start) });
      await page.goto(`${base}/projects/${id}?version=${finalVersion}`); await page.getByRole('heading', { name: 'Demo version 2', exact: true }).waitFor();
      let release; await page.route(`**/api/v1/projects/${id}/versions/${firstVersion}`, async route => { await new Promise(resolve => { release=resolve; }); await route.continue(); });
      await page.evaluate(url => history.pushState(null, '', url), `/projects/${id}?version=${firstVersion}`);
      await until(async () => Boolean(release)); assert.equal(await page.getByRole('heading', { name: 'Demo version 2', exact: true }).count(), 0);
      await page.getByText('Loading saved records…', { exact: true }).waitFor(); release(); await page.getByRole('heading', { name: 'Demo version 1', exact: true }).waitFor();
      assert.equal((await saved(id)).current_version.id, finalVersion); await page.unroute(`**/api/v1/projects/${id}/versions/${firstVersion}`);
    });

    await scenario('foreign and unauthenticated project access returns no project data', async () => {
      const configured = spawnSync(`${root}/apps/api/.venv/bin/python`, ['-c', [
        'import sys,uuid',
        'from f01.db.session import Database',
        'from f01.application.projects import resolve_principal,create_project',
        'from f01.domain.projects import CreateProject',
        'assert "/f01_test_" in sys.argv[1]',
        'database=Database(sys.argv[1])',
        'principal=resolve_principal(database,"phase1-foreign-owner")',
        'created=create_project(database,principal,CreateProject(title="Foreign private title",brief="A private project brief inaccessible to the other owner."),str(uuid.uuid4()))',
        'print(created.model_dump_json())',
        'database.close()',
      ].join('\n'), process.env.M5_TEST_DATABASE_URL], { cwd: `${root}/apps/api`, encoding: 'utf8' });
      assert.equal(configured.status, 0, configured.stderr); const foreign = JSON.parse(configured.stdout).project.id, missing = crypto.randomUUID();
      for (const suffix of ['', '/workspace', '/brain', '/requests', '/events', '/versions', '/runs', '/deployments', '/events/stream']) {
        const unauthorized = await response(`/projects/${foreign}${suffix}`), absent = await response(`/projects/${missing}${suffix}`);
        assert.equal(unauthorized.status, 404); assert.equal(absent.status, 404); const denied = (await unauthorized.json()).error, unavailable = (await absent.json()).error; assert.equal(denied.code, unavailable.code); assert.equal(denied.message, unavailable.message); assert.equal(JSON.stringify(denied).includes('Foreign private title'), false);
      }
      const anonymous = await fetch(`${api}/v1/projects/${id}/workspace`); assert.equal(anonymous.status, 401); assert.equal(JSON.stringify(await anonymous.json()).includes('Phase 1 reviewed'), false);
      await page.goto(`${base}/projects/${foreign}`); await page.getByRole('heading', { name: 'This project is unavailable.', exact: true }).waitFor();
      assert.equal((await page.getByRole('main').innerText()).includes('Foreign private title'), false); await scan(page, 'Unauthorized workspace');
      assert.deepEqual(errors, []);
    });
    await writeFile(`${evidence}/local-baseline.json`, JSON.stringify({ runtime: 'Production Next.js + FastAPI + disposable PostgreSQL 16 on loopback; Chromium headless; 800ms simulation tick; no live model', zoom: '1440×1000 physical-equivalent viewport → 720×500 CSS px at DPR 2 (200% reflow)', measurements }, null, 2)+'\n');
  } finally { await browser?.close(); await stopBrowserServer(server); }
});
