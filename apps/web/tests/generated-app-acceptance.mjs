// Generic functional acceptance for generated apps, driven by QA/multi-app/scenarios.json.
// Observational only: no model calls, no source edits, no route interception or mocks.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {expect} from 'playwright/test';
import {auditGeneratedPage} from './generated-visual-acceptance.mjs';

export const CATALOG = fileURLToPath(new URL('../../../QA/multi-app/scenarios.json', import.meta.url));

export async function loadScenario(id, catalog = CATALOG) {
  const {scenarios} = JSON.parse(await fs.readFile(catalog, 'utf8'));
  const scenario = scenarios.find(item => item.id === id);
  if (!scenario) throw Error(`Unknown acceptance scenario: ${id}`);
  return scenario;
}

const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const numbers = text => (text.match(/\d[\d,]*(?:\.\d+)?/g) ?? []).map(n => Number(n.replaceAll(',', '')));
const dollars = text => (text.match(/\$\s?\d[\d,]*(?:\.\d{1,2})?/g) ?? []).map(n => Number(n.replace(/[$,\s]/g, '')));

// Accept the common semantic containers a model may choose for a labelled collection.
function labelled(page, name) {
  return page.locator(`[aria-label="${name}"]`)
    .or(page.getByRole('region', {name, exact: true}))
    .or(page.getByRole('list', {name, exact: true}))
    .first();
}

async function changes(read, act, timeout = 3000) {
  const before = await read();
  await act();
  await expect.poll(read, {timeout}).not.toEqual(before);
  return {before, after: await read()};
}

async function closeOverlay(page) {
  if (await page.getByRole('dialog').count()) await page.keyboard.press('Escape');
}

// Records page errors, console errors, failed responses and any request outside the preview origin.
export function observeRuntime(page, origin) {
  const runtime = {pageErrors: [], consoleErrors: [], failedRequests: [], externalRequests: []};
  const redact = value => String(value).split(origin).join('[preview]').replace(/\/p\/[^/]+\/[A-Za-z0-9_-]{43}/g, '/p/[id]/[capability]');
  page.on('pageerror', error => runtime.pageErrors.push(redact(error.message).slice(0, 300)));
  page.on('console', message => { if (message.type() === 'error') runtime.consoleErrors.push(redact(message.text()).slice(0, 300)); });
  page.on('request', request => {
    const url = request.url();
    if (!url.startsWith(origin) && !/^(data|blob|about):/.test(url)) runtime.externalRequests.push(url.slice(0, 200));
  });
  page.on('requestfailed', request => runtime.failedRequests.push({url: redact(request.url()).slice(0, 200), reason: request.failure()?.errorText ?? 'failed'}));
  page.on('response', response => { if (response.status() >= 400) runtime.failedRequests.push({url: redact(response.url()).slice(0, 200), status: response.status()}); });
  return runtime;
}

const SCENARIOS = {
  'analytics-dashboard': (page, c) => {
    const metrics = () => labelled(page, c.metrics_region);
    const chart = () => page.locator('svg[role="img"]').filter({has: page.locator('*')}).and(page.locator(`[aria-label^="${c.chart_label_prefix}"]`)).first();
    const reading = async () => ({metrics: await metrics().innerText(), chart: await chart().innerHTML()});
    return [
      ['functional', `Visible "${c.sample_label}" label keeps demonstration data truthful`, async () => {
        await expect(page.getByText(c.sample_label, {exact: false}).first()).toBeVisible();
      }],
      ['functional', `"${c.metrics_region}" shows at least ${c.minimum_metrics} numeric KPIs`, async () => {
        await expect(metrics()).toBeVisible();
        const found = numbers(await metrics().innerText());
        expect(found.length).toBeGreaterThanOrEqual(c.minimum_metrics);
        return {numericValues: found.length};
      }],
      ['functional', `"${c.chart_label_prefix}" chart is a labelled, non-empty SVG`, async () => {
        await expect(chart()).toBeVisible();
        expect(await chart().locator('path, polyline, line, rect, circle').count()).toBeGreaterThan(0);
      }],
      ['functional', `"${c.table}" table lists at least ${c.minimum_table_rows} products`, async () => {
        const table = page.getByRole('table', {name: c.table, exact: true});
        await expect(table).toBeVisible();
        const rows = await table.locator('tbody tr').count() || (await table.getByRole('row').count()) - 1;
        expect(rows).toBeGreaterThanOrEqual(c.minimum_table_rows);
        return {rows};
      }],
      ['functional', `"${c.date_select}" filter updates KPIs and chart`, async () => {
        const select = page.getByLabel(c.date_select, {exact: true});
        const options = await select.locator('option').allInnerTexts();
        for (const option of c.date_options) expect(options.map(o => o.trim())).toContain(option);
        const current = await select.evaluate(el => el.selectedOptions[0]?.textContent?.trim());
        const target = c.date_options.find(option => option !== current);
        const {before, after} = await changes(reading, () => select.selectOption({label: target}));
        expect(after.metrics).not.toEqual(before.metrics);
        expect(after.chart).not.toEqual(before.chart);
      }],
      ['functional', `"${c.region_select}" filter updates KPIs`, async () => {
        const select = page.getByLabel(c.region_select, {exact: true});
        const options = (await select.locator('option').allInnerTexts()).map(o => o.trim());
        expect(options).toContain(c.region_all);
        const specific = options.filter(o => o !== c.region_all);
        expect(specific.length).toBeGreaterThanOrEqual(2);
        await changes(() => metrics().innerText(), () => select.selectOption({label: specific[0]}));
        await select.selectOption({label: c.region_all});
      }],
    ];
  },

  'storefront': (page, c) => {
    const catalog = () => labelled(page, c.products);
    // Innermost product containers only: a model may nest <article> inside <li>.
    const product = () => page.locator('li, article').filter({has: page.getByRole('button', {name: c.add, exact: true})});
    const items = () => catalog().locator('li, article').filter({has: page.getByRole('button', {name: c.add, exact: true})}).filter({hasNot: product()});
    const cartButton = () => page.getByRole('button', {name: new RegExp(`^${escape(c.cart_prefix)}\\b`)}).first();
    const cartCount = async () => numbers(await cartButton().evaluate(el => el.getAttribute('aria-label') || el.textContent || ''))[0] ?? 0;
    const cart = () => page.getByRole('dialog', {name: c.cart}).or(labelled(page, c.cart)).first();
    const search = () => page.getByLabel(c.search, {exact: true});
    const state = {};
    return [
      ['functional', `Visible "${c.sample_label}" label keeps demonstration content truthful`, async () => {
        await expect(page.getByText(c.sample_label, {exact: false}).first()).toBeVisible();
      }],
      ['functional', `"${c.products}" shows at least ${c.minimum_products} priced products`, async () => {
        await expect(catalog()).toBeVisible();
        const texts = await items().allInnerTexts();
        expect(texts.length).toBeGreaterThanOrEqual(c.minimum_products);
        for (const text of texts) expect(dollars(text).length).toBeGreaterThan(0);
        state.total = texts.length;
        state.prices = texts.map(text => dollars(text)[0]);
        return {products: texts.length};
      }],
      ['functional', `"${c.search}" reaches "${c.no_results}" and "${c.clear}" restores the catalog`, async () => {
        await search().fill('zz-no-such-product-qa');
        await expect(items()).toHaveCount(0);
        await expect(page.getByText(c.no_results, {exact: false}).first()).toBeVisible();
        await page.getByRole('button', {name: c.clear, exact: true}).first().click();
        await expect(items()).toHaveCount(state.total);
        await expect(search()).toHaveValue('');
      }],
      ['functional', `"${c.category_select}" filter narrows the catalog`, async () => {
        const select = page.getByLabel(c.category_select, {exact: true});
        const options = (await select.locator('option').allInnerTexts()).map(o => o.trim());
        expect(options).toContain(c.category_all);
        await select.selectOption({label: options.find(o => o !== c.category_all)});
        await expect.poll(() => items().count()).toBeLessThan(state.total);
        expect(await items().count()).toBeGreaterThan(0);
        await select.selectOption({label: c.category_all});
        await expect(items()).toHaveCount(state.total);
      }],
      ['functional', `"${c.details}" opens a named product dialog; Escape restores focus`, async () => {
        const first = items().first();
        const invoker = first.getByRole('button', {name: c.details, exact: true});
        await invoker.click();
        const dialog = page.getByRole('dialog').first();
        await expect(dialog).toBeVisible();
        expect(dollars(await dialog.innerText())).toContain(state.prices[0]);
        await page.keyboard.press('Escape');
        await expect(dialog).toBeHidden();
        await expect(invoker).toBeFocused();
      }],
      ['functional', `"${c.add}" increments the "${c.cart_prefix}" count`, async () => {
        state.start = await cartCount();
        await items().nth(0).getByRole('button', {name: c.add, exact: true}).click();
        await expect.poll(cartCount).toBe(state.start + 1);
        await items().nth(1).getByRole('button', {name: c.add, exact: true}).click();
        await expect.poll(cartCount).toBe(state.start + 2);
      }],
      ['functional', `"${c.cart}" lists items with an accurate "${c.subtotal}"`, async () => {
        await cartButton().click();
        await expect(cart()).toBeVisible();
        const text = await cart().innerText();
        expect(text).toContain(c.subtotal);
        if (state.start === 0) {
          const expected = Math.round((state.prices[0] + state.prices[1]) * 100) / 100;
          expect(dollars(text).some(value => Math.abs(value - expected) < 0.005)).toBe(true);
          return {expectedSubtotal: expected};
        }
      }],
      ['functional', `"${c.remove}" removes an item from the cart`, async () => {
        if (!await cart().isVisible()) await cartButton().click();
        const before = await cartCount();
        await cart().getByRole('button', {name: c.remove, exact: true}).first().click();
        await expect.poll(cartCount).toBe(before - 1);
        await closeOverlay(page);
      }],
      ['functional', 'Cart survives a page reload', async () => {
        const before = await cartCount();
        expect(before).toBeGreaterThan(0);
        await page.reload({waitUntil: 'networkidle'});
        await expect.poll(cartCount).toBe(before);
      }],
    ];
  },

  'social-profile': (page, c) => {
    const feed = () => labelled(page, c.posts);
    const posts = () => feed().locator('article');
    const follow = () => page.getByRole('button', {name: /^Follow(ing)?$/}).first();
    const followers = async () => {
      const text = await page.locator('body').innerText();
      const match = text.match(/([\d,]+)\s*followers/i) ?? text.match(/followers\D{0,4}([\d,]+)/i);
      return match ? Number(match[1].replaceAll(',', '')) : null;
    };
    const like = post => post.getByRole('button', {name: new RegExp(`^${escape(c.like_prefix)}`)}).first();
    const likes = async post => {
      const own = numbers(await like(post).evaluate(el => `${el.textContent ?? ''} ${el.getAttribute('aria-label') ?? ''}`));
      if (own.length) return own[0];
      const match = (await post.innerText()).match(/(\d+)\s*likes?/i);
      return match ? Number(match[1]) : null;
    };
    const unique = `QA acceptance post ${Date.now()}`;
    return [
      ['functional', `Visible "${c.sample_label}" label and "${c.name}" heading`, async () => {
        await expect(page.getByText(c.sample_label, {exact: false}).first()).toBeVisible();
        await expect(page.getByRole('heading', {level: 1, name: c.name})).toBeVisible();
      }],
      ['functional', `"${c.follow}" toggle changes aria-pressed and follower count`, async () => {
        const initial = await followers();
        expect(initial).not.toBeNull();
        const pressed = await follow().getAttribute('aria-pressed');
        expect(['true', 'false']).toContain(pressed);
        const delta = pressed === 'true' ? -1 : 1;
        await follow().click();
        await expect(follow()).toHaveAttribute('aria-pressed', pressed === 'true' ? 'false' : 'true');
        await expect.poll(followers).toBe(initial + delta);
        await follow().click();
        await expect.poll(followers).toBe(initial);
      }],
      ['functional', `Empty "${c.composer}" does not create a post`, async () => {
        const count = await posts().count();
        expect(count).toBeGreaterThan(0);
        await page.getByLabel(c.composer, {exact: true}).fill('');
        const button = page.getByRole('button', {name: c.post, exact: true});
        if (await button.isEnabled()) await button.click();
        await page.waitForTimeout(200);
        await expect(posts()).toHaveCount(count);
      }],
      ['functional', `"${c.post}" publishes a new post first in "${c.posts}"`, async () => {
        const count = await posts().count();
        await page.getByLabel(c.composer, {exact: true}).fill(unique);
        await page.getByRole('button', {name: c.post, exact: true}).click();
        await expect(posts()).toHaveCount(count + 1);
        await expect(posts().first()).toContainText(unique);
      }],
      ['functional', `"${c.like_prefix}" toggle changes aria-pressed and like count`, async () => {
        const post = posts().first();
        const before = await likes(post);
        expect(before).not.toBeNull();
        await like(post).click();
        await expect(like(post)).toHaveAttribute('aria-pressed', 'true');
        await expect.poll(() => likes(post)).toBe(before + 1);
      }],
      ['functional', 'New post and like survive a page reload', async () => {
        await page.reload({waitUntil: 'networkidle'});
        const post = posts().filter({hasText: unique});
        await expect(post).toHaveCount(1);
        await expect(like(post)).toHaveAttribute('aria-pressed', 'true');
      }],
    ];
  },
};

// Runs one scenario in a fresh browser context; returns a report and writes acceptance.json.
export async function runScenarioAcceptance(browser, scenario, {url, directory, checkTimeout = 8000}) {
  if (!SCENARIOS[scenario.id]) throw Error(`No checks for scenario ${scenario.id}`);
  await fs.mkdir(directory, {recursive: true});
  const context = await browser.newContext({viewport: {width: 1440, height: 900}});
  const report = {scenario: scenario.id, checks: [], runtime: null, visual: null};
  try {
    const page = await context.newPage();
    page.setDefaultTimeout(checkTimeout);
    report.runtime = observeRuntime(page, new URL(url).origin);
    await page.goto(url, {waitUntil: 'networkidle', timeout: 20000});
    const record = async (category, name, fn) => {
      try {
        const evidence = await fn();
        report.checks.push({category, name, passed: true, evidence: evidence ?? null});
      } catch (error) {
        report.checks.push({category, name, passed: false, error: String(error.message).split(url).join('[preview]').slice(0, 600)});
        await closeOverlay(page).catch(() => {});
      }
    };
    for (const [category, name, fn] of SCENARIOS[scenario.id](page, scenario.contract)) await record(category, name, fn);
    await record('visual', 'Responsive measurements pass at four widths', async () => {
      await page.reload({waitUntil: 'networkidle'});
      report.visual = await auditGeneratedPage(page, {directory: path.join(directory, 'visual'), primarySelector: scenario.primary_selector});
      expect(report.visual.deterministicPassed).toBe(true);
    });
    await record('accessibility', 'Automated WCAG A/AA scan reports no violations', async () => {
      expect(report.visual?.accessibilityPassed).toBe(true);
    });
    await record('runtime', 'No uncaught exceptions or console errors', async () => {
      expect(report.runtime.pageErrors).toEqual([]);
      expect(report.runtime.consoleErrors).toEqual([]);
    });
    await record('runtime', 'No failed or external network requests', async () => {
      expect(report.runtime.failedRequests).toEqual([]);
      expect(report.runtime.externalRequests).toEqual([]);
    });
  } finally {
    await context.close();
    report.passed = report.checks.length > 0 && report.checks.every(check => check.passed);
    report.summary = Object.fromEntries(['functional', 'visual', 'accessibility', 'runtime'].map(category => {
      const rows = report.checks.filter(check => check.category === category);
      return [category, {passed: rows.filter(check => check.passed).length, total: rows.length}];
    }));
    report.subjectiveReviewRequired = 'Screenshots need human review; passing checks do not certify premium design.';
    await fs.writeFile(path.join(directory, 'acceptance.json'), JSON.stringify(report, null, 2));
  }
  return report;
}

// CLI: the private preview URL comes from the environment and is never printed.
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  let browser;
  try {
    const {chromium} = await import('playwright');
    const url = process.env.F01_GENERATED_PREVIEW_URL;
    if (!url) throw Error('Missing preview');
    const parsed = new URL(url);
    if (parsed.protocol !== 'http:' || parsed.username || parsed.password || !(parsed.hostname === 'localhost' || parsed.hostname.endsWith('.localhost') || parsed.hostname === '127.0.0.1')) throw Error('Invalid local preview');
    const scenario = await loadScenario(process.env.F01_ACCEPTANCE_SCENARIO ?? '');
    browser = await chromium.launch({headless: true});
    const report = await runScenarioAcceptance(browser, scenario, {url, directory: process.env.F01_ACCEPTANCE_OUTPUT || `.runtime/multi-app/${scenario.id}/browser`});
    console.log(JSON.stringify({scenario: scenario.id, passed: report.passed, summary: report.summary, failed: report.checks.filter(check => !check.passed).map(check => check.name)}));
    if (!report.passed) process.exitCode = 1;
  } catch (error) {
    console.error(`Generated app acceptance could not complete: ${String(error.message).startsWith('Unknown acceptance scenario') ? error.message : 'check the private local preview URL, scenario and installed Chromium.'}`);
    process.exitCode = 2;
  } finally { await browser?.close(); }
}
