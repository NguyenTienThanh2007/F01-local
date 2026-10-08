import {stopBrowserServer,launchTestBrowser} from './browser-process.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { readdir, readFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { projectPlan } from './fixtures/project-plan.mjs';

const webRoot = fileURLToPath(new URL('../', import.meta.url));
const token = 'synthetic-browser-test-token-1234567890';

async function listen(server) {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return server.address().port;
}
async function waitUntil(check, limit = 30_000) {
  const deadline = Date.now() + limit;
  while (Date.now() < deadline) {
    if (await check().catch(() => false)) return;
    await delay(100);
  }
  throw new Error('Application did not reach the expected state.');
}
async function jsFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = await Promise.all(entries.map(entry => entry.isDirectory() ? jsFiles(join(dir, entry.name)) : entry.name.endsWith('.js') ? [join(dir, entry.name)] : []));
  return files.flat();
}

test('production frontend submits, displays, recovers and protects the browser boundary', { timeout: 150_000 }, async t => {
  async function run(name, scenario) {
    let failure;
    await t.test(name, async () => {
      try { await scenario(); } catch (error) { failure = error; throw error; }
    });
    if (failure) throw new Error(`Browser scenario failed: ${name}`);
  }
  let mode = 'success';
  let calls = 0;
  let pendingResponses = [];
  const backend = createServer(async (req, res) => {
    if (req.method !== 'POST' || req.url !== '/v1/plan' || req.headers.authorization !== `Bearer ${token}`) {
      res.writeHead(401).end(); return;
    }
    let raw = '';
    for await (const chunk of req) raw += chunk;
    const input = JSON.parse(raw);
    assert.deepEqual(Object.keys(input), ['idea']);
    assert.equal(typeof input.idea, 'string');
    calls++;
    res.setHeader('Content-Type', 'application/json');
    const respond = () => {
      if (mode === 'success') res.end(JSON.stringify(projectPlan));
      else if (mode === 'invalid') res.end('{"project_title":"Incomplete"}');
      else {
        res.statusCode = 503;
        res.end(JSON.stringify({ error: { code: mode, message: 'unsafe-upstream-message', request_id: '00000000-0000-4000-8000-000000000001' } }));
      }
    };
    if (mode === 'pending') pendingResponses.push(res);
    else respond();
  });
  let frontend;
  let browser;
  try {
    const backendPort = await listen(backend);
    const probe = createServer();
    const frontendPort = await listen(probe);
    await new Promise(resolve => probe.close(resolve));
    const base = `http://127.0.0.1:${frontendPort}`;
    const env = { ...process.env, APP_ENV: 'test', AUTH_MODE: 'development', EXECUTION_MODE: 'simulated', DEV_API_TOKEN: token, API_INTERNAL_URL: `http://127.0.0.1:${backendPort}`, NEXT_PUBLIC_APP_URL: base };
    delete env.OPENAI_API_KEY;
    frontend = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', String(frontendPort)], { cwd: webRoot, env, stdio: 'ignore' });
    await waitUntil(async () => (await fetch(`${base}/projects/new`)).ok);
    browser = await launchTestBrowser({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    const browserPosts = [];
    page.on('request', req => { if (req.method() === 'POST') browserPosts.push(req); });
    await page.goto(`${base}/projects/new?planning=1`);
    const brief = page.getByRole('textbox', { name: 'Product brief' });
    const alert = page.getByRole('main').getByRole('alert');
    const submit = page.getByRole('button', { name: 'Create plan', exact: true });

    await run('blank and oversized ideas are validated without network access', async () => {
      await submit.click();
      assert.equal(await brief.getAttribute('aria-invalid'), 'true');
      assert.equal(await brief.evaluate(element => element === document.activeElement), true);
      assert.match(await alert.innerText(), /1–10,000/);
      await brief.fill('x'.repeat(10_001));
      await submit.click();
      assert.equal(calls, 0);
      await brief.fill('Build a CRM for real estate agents with leads and notes.');
    });

    await run('pending state prevents duplicate submissions and cancellation preserves the brief', async () => {
      mode = 'pending';
      await submit.click();
      await waitUntil(async () => calls === 1 || await page.locator('.planning-error').isVisible());
      assert.equal(calls, 1, await page.locator('.planning-error').isVisible() ? await page.locator('.planning-error').innerText() : 'Expected one backend call.');
      assert.equal(await page.getByRole('button', { name: 'Creating plan…' }).isDisabled(), true);
      assert.equal(await brief.getAttribute('readonly'), '');
      assert.match(await page.getByRole('status').innerText(), /Planning/);
      await page.getByRole('button', { name: 'Cancel', exact: true }).click();
      assert.match(await brief.inputValue(), /real estate/);
      assert.equal(await submit.isEnabled(), true);
      for (const response of pendingResponses) response.end(JSON.stringify(projectPlan));
      pendingResponses = [];
      await delay(100);
      assert.equal(await page.getByRole('heading', { name: 'Harbor CRM' }).count(), 0);
    });

    await run('successful request renders all structured plan fields and keeps credentials server-side', async () => {
      mode = 'success';
      await submit.click();
      await page.getByRole('heading', { name: 'Harbor CRM', exact: true }).waitFor();
      assert.equal(calls, 2);
      assert.match(await page.getByRole('status').innerText(), /Plan ready/);
      for (const title of ['Target users', 'Core features', 'Recommended stack', 'Implementation milestones']) assert.equal(await page.getByRole('heading', { name: title, exact: true }).count(), 1);
      const plan = page.getByRole('article');
      const text = await plan.innerText();
      for (const value of [projectPlan.product_summary, ...projectPlan.target_users, ...projectPlan.core_features.flatMap(feature => [feature.name, feature.description]), ...Object.values(projectPlan.recommended_stack), ...projectPlan.implementation_milestones.flatMap(item => [item.title, ...item.deliverables])]) assert.ok(text.includes(value));
      assert.match(text, /Not saved · No build started/);
      assert.equal(await page.locator('.planning-result').evaluate(element => element === document.activeElement), true);
      assert.ok(!(await page.content()).includes(token));
      for (const req of browserPosts) {
        assert.equal(req.url(), `${base}/api/v1/plan`);
        assert.equal(req.headers().authorization, undefined);
        assert.ok(!req.postData().includes(token));
      }
      await mkdir(join(webRoot, 'test-results'), { recursive: true });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: join(webRoot, 'test-results/planning-desktop.png'), fullPage: true });
      for (const width of [375, 768, 1280, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      }
      await page.setViewportSize({ width: 375, height: 900 });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: join(webRoot, 'test-results/planning-mobile.png'), fullPage: true });
      await brief.fill('Build a different CRM.');
      assert.match(await page.locator('.plan-stale').innerText(), /submitted brief/);
    });

    await run('provider failures preserve input and a retry renders a new successful plan', async () => {
      for (const code of ['PROVIDER_NOT_CONFIGURED', 'PROVIDER_AUTHENTICATION_FAILED', 'PROVIDER_QUOTA_EXCEEDED', 'PROVIDER_RATE_LIMITED', 'PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE', 'PROVIDER_REFUSED']) {
        mode = code;
        await page.getByRole('button', { name: /Create (another )?plan/ }).click();
        await alert.waitFor();
        assert.ok(!(await alert.innerText()).includes('unsafe-upstream-message'));
        assert.equal(await brief.inputValue(), 'Build a different CRM.');
        assert.equal(await submit.isEnabled(), true);
      }
      mode = 'invalid';
      await submit.click();
      await alert.waitFor();
      assert.match(await alert.innerText(), /invalid plan/);
      mode = 'success';
      await submit.click();
      await page.getByRole('heading', { name: 'Harbor CRM', exact: true }).waitFor();
      assert.match(await page.getByRole('status').innerText(), /Plan ready/);
    });

    await run('HTML-like provider text is displayed as text', async () => {
      const original = projectPlan.product_summary;
      try {
        projectPlan.product_summary = '<img src=x onerror="window.__unsafe=true">';
        await page.getByRole('button', { name: 'Create another plan' }).click();
        await waitUntil(async () => (await page.getByRole('article').innerText()).includes('<img'));
        assert.equal(await page.getByRole('article').locator('img').count(), 0);
        assert.equal(await page.evaluate(() => window.__unsafe), undefined);
      } finally { projectPlan.product_summary = original; }
    });

    await run('the real route rejects cross-site requests and unsupported methods', async () => {
      const before = calls;
      const response = await fetch(`${base}/api/v1/plan`, { method: 'POST', headers: { Origin: 'https://attacker.invalid', 'Content-Type': 'application/json' }, body: '{"idea":"CRM"}' });
      assert.equal(response.status, 403);
      assert.equal((await fetch(`${base}/api/v1/plan`)).status, 405);
      assert.equal(calls, before);
    });

    await run('homepage starters change the brief and labeled sample without making a backend request', async () => {
      const before = calls;
      await page.goto(base);
      assert.match(await page.getByRole('heading', { level: 1 }).innerText(), /Big idea\.\s*Real application\./);
      assert.match(await page.locator('.welcome-promise > p').innerText(), /Try it before you publish/);
      await page.locator('.welcome-draft > summary').click();
      assert.equal(await page.getByRole('button', { name: 'Play demo' }).count(), 1);
      assert.match(await page.locator('.demo-trace > p').innerText(), /No application, build or deployment is executed/);
      for (const [title, expected, sample] of [
        ['A clearer sales pipeline', 'real estate', 'Harbor / CRM'],
        ['Fewer missed appointments', 'missed appointments', 'Studio / daybook'],
        ['One more round', 'geometric maze', 'CHECKPOINT'],
      ]) {
        const starter = page.getByRole('button', { name: new RegExp(title) });
        await starter.click();
        assert.equal(await starter.getAttribute('aria-pressed'), 'true');
        assert.match(await page.getByRole('textbox', { name: 'Product brief' }).inputValue(), new RegExp(expected));
        assert.ok((await page.locator('.sample-frame').innerText()).includes(sample));
      }
      assert.equal(calls, before);
      await waitUntil(() => page.getByRole('textbox', { name: 'Product brief' }).evaluate(element => element === document.activeElement));
      mode = 'success';
      await page.getByRole('button', { name: 'Create plan', exact: true }).click();
      await page.getByRole('heading', { name: 'Harbor CRM', exact: true }).waitFor();
      assert.equal(calls, before + 1);
      assert.equal(await page.getByRole('article').count(), 1);
      assert.match(await page.getByRole('article').innerText(), /Not saved · No build started/);
    });

    await run('global navigation exposes real starter briefs, planned connections and documentation', async () => {
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.goto(base);
      const navigation = page.getByRole('navigation', { name: 'Global navigation' }).first();
      for (const [name, href] of [['Projects', '/projects'], ['Examples', '#templates'], ['Docs', '#docs']]) {
        assert.equal(await navigation.getByRole('link', { name: new RegExp(name) }).getAttribute('href'), href);
      }
      assert.equal(await page.locator('.os-account').getAttribute('href'), '/account');
      await page.locator('.welcome-advanced > summary').click();
      assert.match(await page.locator('#connections').innerText(), /PLANNED/);
      assert.match(await page.locator('#connections').innerText(), /No connections can be authorized/);
      await navigation.getByRole('link', { name: 'Examples', exact: true }).click();
      await page.locator('#templates').waitFor();
      assert.match(await page.locator('#templates').innerText(), /Choose a brief/);
      assert.equal(await page.locator('.welcome-promise').getByRole('link',{name:/Create a project/}).getAttribute('href'),'/projects/new');
      const before = calls;
      await page.setViewportSize({ width: 375, height: 1000 });
      const menu = page.getByRole('button', { name: 'Open global navigation' });
      await menu.focus(); await page.keyboard.press('Enter');
      await page.getByRole('dialog', { name: 'Explore F01' }).waitFor();
      assert.equal(await page.getByRole('dialog').getByRole('link', { name: /Examples/ }).count(), 1);
      await page.keyboard.press('Escape');
      await page.getByRole('dialog').waitFor({ state: 'hidden' });
      assert.equal(await menu.evaluate(element => element === document.activeElement), true);
      assert.equal(calls, before);
    });

    await run('sample workspace views and evidence inspection are interactive without executing work', async () => {
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.goto(base);
      const before = calls;
      await page.locator('.welcome-draft > summary').click();
      await page.getByRole('button', { name: 'Blueprint', exact: true }).click();
      assert.match(await page.locator('.sample-frame').innerText(), /SAMPLE BLUEPRINT \/ NOT GENERATED/);
      assert.match(await page.locator('.sample-blueprint').innerText(), /shared lead register/);
      const fullWidth = (await page.locator('.sample-frame').boundingBox()).width;
      await page.getByRole('button', { name: 'Compact view', exact: false }).click();
      await delay(200);
      assert.ok((await page.locator('.sample-frame').boundingBox()).width < fullWidth);
      await page.getByRole('button', { name: 'Full view', exact: false }).click();
      await page.getByRole('button', { name: 'Preview', exact: true }).click();
      assert.match(await page.locator('.sample-frame').innerText(), /Harbor \/ CRM/);
      const evidence = page.getByRole('button', { name: /Application structure prepared/ });
      await evidence.click();
      assert.equal(await evidence.getAttribute('aria-pressed'), 'true');
      assert.match(await page.locator('.demo-workspace-heading .project-pulse').innerText(), /Building/);
      assert.match(await page.locator('.trace-receipt').innerText(), /No code is generated/);
      assert.equal(calls, before);
    });

    await run('demo can pause and replay and is static by default with reduced motion', async () => {
      await page.goto(base);
      await page.locator('.welcome-draft > summary').click();
      const pulse = page.locator('.demo-workspace-heading .project-pulse');
      assert.match(await pulse.innerText(), /Understanding/);
      await delay(2100);
      assert.match(await pulse.innerText(), /Understanding/);
      await page.getByRole('button', { name: 'Play demo' }).click();
      await waitUntil(async () => (await pulse.innerText()).includes('Planning'));
      await page.getByRole('button', { name: 'Pause demo' }).click();
      await delay(2100);
      assert.match(await pulse.innerText(), /Planning/);
      await page.getByRole('button', { name: 'Play demo' }).click();
      await page.getByRole('button', { name: 'Replay demo' }).waitFor();
      assert.match(await pulse.innerText(), /Live/);
      await page.getByRole('button', { name: 'Replay demo' }).click();
      assert.match(await pulse.innerText(), /Understanding/);
      await page.getByRole('button', { name: 'Pause demo' }).click();
      await page.emulateMedia({ reducedMotion: 'no-preference' });
      await page.goto(base);
      await page.locator('.welcome-draft > summary').click();
      await page.getByRole('button', { name: 'Pause demo' }).waitFor();
      await waitUntil(async () => (await pulse.innerText()).includes('Planning'));
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.getByRole('button', { name: 'Play demo' }).waitFor();
    });

    await run('dashboard exposes a retryable connection error and starters prefill creation', async () => {
      await page.goto(`${base}/projects`);
      await page.getByRole('link', { name: 'Sign in to your workspace' }).waitFor();
      assert.equal(await page.getByRole('searchbox', { name: 'Search projects' }).isDisabled(), false);
      await page.locator('.dashboard-filters > summary').click();
      assert.equal(await page.getByRole('combobox', { name: 'Project state' }).isDisabled(), false);
      await page.locator('.dashboard-starters > summary').click();
      const before = calls;
      await page.getByRole('link', { name: /Fewer missed appointments/ }).click();
      assert.match(await page.getByRole('textbox', { name: 'Product brief' }).inputValue(), /missed appointments/);
      assert.equal(await page.getByRole('button', { name: /Fewer missed appointments/ }).getAttribute('aria-pressed'), 'true');
      assert.equal(calls, before);
      await page.goto(`${base}/projects/new?starter=unknown`);
      await page.getByText('Your draft is back. Review it before creating your project.',{exact:true}).waitFor();
      assert.match(await page.getByRole('textbox', { name: 'Product brief' }).inputValue(), /missed appointments/);
    });

    await run('all redesigned surfaces fit target widths and mobile navigation restores keyboard focus', async () => {
      await mkdir(join(webRoot, 'test-results/redesign'), { recursive: true });
      for (const [route, name] of [['', 'home'], ['/projects', 'projects'], ['/projects/new', 'create']]) {
        for (const width of [375, 768, 1280, 1440]) {
          await page.setViewportSize({ width, height: 1000 });
          await page.goto(`${base}${route}`);
          await page.evaluate(() => document.fonts.ready);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, `${name}: ${width}px overflow`);
          assert.equal(await page.getByRole('main').count(), 1);
          assert.equal(await page.getByRole('heading', { level: 1 }).count(), 1);
          await page.screenshot({ path: join(webRoot, `test-results/redesign/${name}-${width}.png`), fullPage: true });
        }
      }
      await page.setViewportSize({ width: 375, height: 1000 });
      await page.goto(`${base}/projects/new?planning=1`);
      const open = page.getByRole('button', { name: 'Open navigation' });
      await open.focus();
      await page.keyboard.press('Enter');
      await page.getByRole('dialog', { name: 'Navigation' }).waitFor();
      await page.keyboard.press('Escape');
      await page.getByRole('dialog', { name: 'Navigation' }).waitFor({ state: 'hidden' });
      assert.equal(await open.evaluate(element => element === document.activeElement), true);
      assert.notEqual(await open.evaluate(element => getComputedStyle(element).outlineStyle), 'none');
    });

    await run('production browser JavaScript contains no credential environment references', async () => {
      for (const path of await jsFiles(join(webRoot, '.next/static'))) {
        const source = await readFile(path, 'utf8');
        assert.ok(!source.includes('DEV_API_TOKEN'));
        assert.ok(!source.includes('OPENAI_API_KEY'));
        assert.ok(!source.includes(token));
      }
    });
  } finally {
    for (const response of pendingResponses) response.destroy();
    await browser?.close();
    const stopped=stopBrowserServer(frontend);
    backend.closeAllConnections();
    await new Promise(resolve => backend.close(resolve));
    await stopped;
  }
});
